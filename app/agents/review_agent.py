"""Review agent node — handles DB reads/writes for plans and progress."""

import asyncio
import os
from typing import Any

from langchain_mcp_adapters import client as mcp_client

from app.config import settings
from app.db.repository_factory import get_repository
from app.db.mcp_repository import _extract_rows, _inline_params
from app.mcp.client import extract_payload
from app.models.state import GraphState


def review_node(state: GraphState) -> dict:
    """Execute DB action plan and return a user response."""
    # TODO: Add disambiguation prompt when multiple plans share titles and no plan_id is chosen.
    # TODO: Return explicit confirmation after status updates (e.g., "Updated X to in_progress").
    db_plan = _normalize_plan(state.get("db_plan"))
    db_context = state.get("db_context") or {}
    if not db_plan and db_context:
        response = _format_db_response(db_context, state.get("user_input", ""))
        return {
            "user_response": response,
            "specialist_output": response,
            "db_context": db_context,
        }
    if settings.db_backend.lower() == "mcp":
        return asyncio.run(_review_mcp(state))
    return _review_psycopg(state)


def _review_psycopg(state: GraphState) -> dict:
    repo = get_repository()
    db_plan = _normalize_plan(state.get("db_plan"))
    db_context: dict[str, Any] = {}

    for step in db_plan:
        action = step.get("action")
        if action == "get_plans":
            db_context["plans"] = repo.get_plans()
        elif action == "get_plan_items":
            plan_id = step.get("plan_id")
            plan_title = step.get("plan_title")
            if plan_title:
                db_context["requested_plan_title"] = plan_title
            db_context["requested_items"] = True
            if plan_title and plan_id == "latest":
                plan_id = None
            if plan_id == "latest":
                plan_id = repo.get_latest_plan_id()
            if plan_id is None and plan_title:
                plans = db_context.get("plans") or repo.get_plans()
                db_context.setdefault("plans", plans)
                candidate_ids = _resolve_plan_ids(plans, plan_title)
                found = False
                for candidate_id in candidate_ids:
                    items = repo.get_plan_items(candidate_id)
                    if items:
                        db_context["requested_plan_id"] = candidate_id
                        db_context.setdefault("plan_items", {})[candidate_id] = items
                        found = True
                        break
                if not found and candidate_ids:
                    candidate_id = candidate_ids[0]
                    db_context["requested_plan_id"] = candidate_id
                    db_context.setdefault("plan_items", {})[candidate_id] = repo.get_plan_items(candidate_id)
            elif plan_id is not None:
                db_context["requested_plan_id"] = plan_id
                db_context.setdefault("plan_items", {})[plan_id] = repo.get_plan_items(plan_id)
        elif action == "create_plan":
            title = step.get("title", "Study Plan")
            db_context["created_plan_id"] = repo.create_plan(title)
        elif action == "add_plan_item":
            plan_id = step.get("plan_id")
            if plan_id == "latest":
                plan_id = repo.get_latest_plan_id()
            due_date = step.get("due_date") or None
            notes = step.get("notes") or None
            repo.add_plan_item(
                plan_id=plan_id,
                title=step.get("title", "Plan item"),
                topic_id=None,
                due_date=due_date,
                notes=notes,
            )
        elif action == "update_plan_item_status":
            item_id = step.get("item_id")
            status = step.get("status", "in_progress")
            plan_id = step.get("plan_id")
            plan_title = step.get("plan_title")
            item_title = step.get("item_title")
            if item_id is None and plan_id == "latest":
                plan_id = repo.get_latest_plan_id()
            if item_id is None and plan_id is None and plan_title:
                plans = db_context.get("plans") or repo.get_plans()
                db_context.setdefault("plans", plans)
                candidate_ids = _resolve_plan_ids(plans, plan_title)
                plan_id = candidate_ids[0] if candidate_ids else None
            if item_id is None and plan_id is None:
                plan_id = repo.get_latest_plan_id()
            if item_id is None and plan_id is not None and item_title:
                items = repo.get_plan_items(plan_id)
                item_id = _resolve_item_id(items, item_title)
            if item_id is not None:
                repo.update_plan_item_status(item_id, status)
        elif action == "update_plan_items_status":
            plan_id = step.get("plan_id")
            if plan_id == "latest":
                plan_id = repo.get_latest_plan_id()
            if plan_id is not None:
                for item in repo.get_plan_items(plan_id):
                    repo.update_plan_item_status(item["item_id"], step.get("status", "in_progress"))

    response = _format_db_response(db_context, state.get("user_input", ""))
    return {
        "user_response": response,
        "specialist_output": response,
        "db_context": db_context,
    }


async def _review_mcp(state: GraphState) -> dict:
    db_plan = _normalize_plan(state.get("db_plan"))
    db_context: dict[str, Any] = {}

    connection = _build_mcp_connection()
    async with mcp_client.create_session(connection) as session:
        await session.initialize()

        async def _call(sql: str, params: list | None = None):
            params = params or []
            if params and not settings.mcp_supports_params:
                sql = _inline_params(sql, params)
                params = []
            args = {settings.mcp_query_key: sql}
            if settings.mcp_supports_params and params:
                args[settings.mcp_params_key] = params
            result = await session.call_tool(settings.mcp_tool_name, args)
            payload = extract_payload(result)
            return _extract_rows(payload)

        for step in db_plan:
            action = step.get("action")
            if action == "get_plans":
                rows = await _call("SELECT plan_id, title, created_at FROM study_plan ORDER BY created_at DESC")
                db_context["plans"] = rows
            elif action == "get_plan_items":
                plan_id = step.get("plan_id")
                plan_title = step.get("plan_title")
                if plan_title:
                    db_context["requested_plan_title"] = plan_title
                db_context["requested_items"] = True
                if plan_title and plan_id == "latest":
                    plan_id = None
                if plan_id == "latest":
                    latest = await _call("SELECT plan_id FROM study_plan ORDER BY created_at DESC LIMIT 1")
                    plan_id = latest[0]["plan_id"] if latest else None
                if plan_id is None and plan_title:
                    plans = db_context.get("plans")
                    if plans is None:
                        plans = await _call("SELECT plan_id, title, created_at FROM study_plan ORDER BY created_at DESC")
                        db_context["plans"] = plans
                    candidate_ids = _resolve_plan_ids(plans, plan_title)
                    found = False
                    for candidate_id in candidate_ids:
                        items = await _call(
                            "SELECT item_id, plan_id, topic_id, title, status, due_date, notes "
                            "FROM plan_items WHERE plan_id = %s ORDER BY item_id",
                            [candidate_id],
                        )
                        if items:
                            db_context["requested_plan_id"] = candidate_id
                            db_context.setdefault("plan_items", {})[candidate_id] = items
                            found = True
                            break
                    if not found and candidate_ids:
                        candidate_id = candidate_ids[0]
                        db_context["requested_plan_id"] = candidate_id
                        items = await _call(
                            "SELECT item_id, plan_id, topic_id, title, status, due_date, notes "
                            "FROM plan_items WHERE plan_id = %s ORDER BY item_id",
                            [candidate_id],
                        )
                        db_context.setdefault("plan_items", {})[candidate_id] = items
                elif plan_id is not None:
                    db_context["requested_plan_id"] = plan_id
                    items = await _call(
                        "SELECT item_id, plan_id, topic_id, title, status, due_date, notes "
                        "FROM plan_items WHERE plan_id = %s ORDER BY item_id",
                        [plan_id],
                    )
                    db_context.setdefault("plan_items", {})[plan_id] = items
            elif action == "create_plan":
                title = step.get("title", "Study Plan")
                rows = await _call("INSERT INTO study_plan (title) VALUES (%s) RETURNING plan_id", [title])
                db_context["created_plan_id"] = rows[0]["plan_id"] if rows else None
            elif action == "add_plan_item":
                plan_id = step.get("plan_id")
                if plan_id == "latest":
                    latest = await _call("SELECT plan_id FROM study_plan ORDER BY created_at DESC LIMIT 1")
                    plan_id = latest[0]["plan_id"] if latest else None
                due_date = step.get("due_date") or None
                notes = step.get("notes") or None
                await _call(
                    "INSERT INTO plan_items (plan_id, topic_id, title, due_date, notes) VALUES (%s, %s, %s, %s, %s)",
                    [plan_id, None, step.get("title", "Plan item"), due_date, notes],
                )
            elif action == "update_plan_item_status":
                item_id = step.get("item_id")
                status = step.get("status", "in_progress")
                plan_id = step.get("plan_id")
                plan_title = step.get("plan_title")
                item_title = step.get("item_title")
                if item_id is None and plan_id == "latest":
                    latest = await _call("SELECT plan_id FROM study_plan ORDER BY created_at DESC LIMIT 1")
                    plan_id = latest[0]["plan_id"] if latest else None
                if item_id is None and plan_id is None and plan_title:
                    plans = db_context.get("plans")
                    if plans is None:
                        plans = await _call("SELECT plan_id, title, created_at FROM study_plan ORDER BY created_at DESC")
                        db_context["plans"] = plans
                    candidate_ids = _resolve_plan_ids(plans, plan_title)
                    plan_id = candidate_ids[0] if candidate_ids else None
                if item_id is None and plan_id is None:
                    latest = await _call("SELECT plan_id FROM study_plan ORDER BY created_at DESC LIMIT 1")
                    plan_id = latest[0]["plan_id"] if latest else None
                if item_id is None and plan_id is not None and item_title:
                    items = await _call(
                        "SELECT item_id, title FROM plan_items WHERE plan_id = %s ORDER BY item_id",
                        [plan_id],
                    )
                    item_id = _resolve_item_id(items, item_title)
                if item_id is not None:
                    await _call("UPDATE plan_items SET status = %s WHERE item_id = %s", [status, item_id])
            elif action == "update_plan_items_status":
                plan_id = step.get("plan_id")
                if plan_id == "latest":
                    latest = await _call("SELECT plan_id FROM study_plan ORDER BY created_at DESC LIMIT 1")
                    plan_id = latest[0]["plan_id"] if latest else None
                if plan_id is not None:
                    await _call("UPDATE plan_items SET status = %s WHERE plan_id = %s", [step.get("status", "in_progress"), plan_id])

    response = _format_db_response(db_context, state.get("user_input", ""))
    return {
        "user_response": response,
        "specialist_output": response,
        "db_context": db_context,
    }


def _format_db_response(db_context: dict[str, Any], user_input: str) -> str:
    plans = db_context.get("plans")
    items_map = db_context.get("plan_items")
    requested_plan_id = db_context.get("requested_plan_id")
    requested_plan_title = db_context.get("requested_plan_title")
    requested_items = bool(db_context.get("requested_items"))

    if plans is None and items_map is None:
        return "Done."

    if plans is None:
        plans = []
    if items_map is None:
        items_map = {}

    if not plans:
        return "No learning plans found."

    items_only = requested_items or bool(requested_plan_id or requested_plan_title)
    if items_only:
        plan_id = requested_plan_id
        plan_title = requested_plan_title
        matching_ids: list[int] = []
        if plan_id is None and plan_title:
            matching_ids = _resolve_plan_ids(plans, plan_title)
            if matching_ids:
                plan_id = matching_ids[0]
        if plan_id is None:
            return "Which plan do you want the items for?"
        if not matching_ids:
            matching_ids = [plan_id]

        lines = ["Here are the items for your plan(s):"]
        found_any = False
        for candidate_id in matching_ids:
            items = items_map.get(candidate_id, [])
            if not items:
                continue
            found_any = True
            created_at = _lookup_plan_created_at(plans, candidate_id)
            header = f"Plan ID {candidate_id}"
            if created_at:
                header += f" (created {created_at})"
            lines.append(header + ":")
            for item in items:
                item_title = item.get("title", "Plan item")
                status = item.get("status", "pending")
                lines.append(f"- {item_title} [{status}]")
        if not found_any:
            return "No items found for the requested plan."
        return "\n".join(lines)

    has_items = bool(items_map)
    lines = ["Here are your learning plans:" if not has_items else "Here are your plans with items:"]
    seen_ids: set[int] = set()
    seen_titles: set[str] = set()
    for plan in plans:
        title = plan.get("title", "Untitled plan")
        plan_id = plan.get("plan_id")
        if plan_id is not None:
            if plan_id in seen_ids:
                continue
            seen_ids.add(plan_id)
        else:
            lowered = str(title).lower()
            if lowered in seen_titles:
                continue
            seen_titles.add(lowered)
        lines.append(f"- {title}")
        if has_items and plan_id in items_map:
            for item in items_map.get(plan_id, []):
                item_title = item.get("title", "Plan item")
                status = item.get("status", "pending")
                lines.append(f"  - {item_title} [{status}]")
    if has_items and not items_map:
        lines.append("No items found for the requested plan.")
    return "\n".join(lines)


def _resolve_plan_id(plans: list[dict[str, Any]], plan_title: str) -> int | None:
    if not plans:
        return None
    lowered = plan_title.lower()
    for plan in plans:
        title = str(plan.get("title", "")).lower()
        if title == lowered:
            return plan.get("plan_id")
    for plan in plans:
        title = str(plan.get("title", "")).lower()
        if lowered in title:
            return plan.get("plan_id")
    return None


def _resolve_plan_ids(plans: list[dict[str, Any]], plan_title: str) -> list[int]:
    if not plans:
        return []
    lowered = plan_title.lower()
    exact = []
    contains = []
    for plan in plans:
        title = str(plan.get("title", "")).lower()
        plan_id = plan.get("plan_id")
        if plan_id is None:
            continue
        if title == lowered:
            exact.append(plan_id)
        elif lowered in title:
            contains.append(plan_id)
    return exact + contains


def _lookup_plan_created_at(plans: list[dict[str, Any]], plan_id: int) -> str | None:
    for plan in plans:
        if plan.get("plan_id") == plan_id:
            return plan.get("created_at")
    return None


def _resolve_item_id(items: list[dict[str, Any]], item_title: str) -> int | None:
    if not items:
        return None
    lowered = item_title.lower()
    for item in items:
        title = str(item.get("title", "")).lower()
        if title == lowered:
            return item.get("item_id")
    for item in items:
        title = str(item.get("title", "")).lower()
        if lowered in title:
            return item.get("item_id")
    return None




def _normalize_plan(db_plan: Any) -> list[dict[str, Any]]:
    if not db_plan:
        return []
    normalized: list[dict[str, Any]] = []
    for step in db_plan:
        if hasattr(step, "model_dump"):
            normalized.append(step.model_dump())
        elif isinstance(step, dict):
            normalized.append(step)
        else:
            try:
                normalized.append(dict(step))
            except Exception:
                continue
    return normalized


def _build_mcp_connection() -> dict:
    from app.mcp.manager import _parse_args

    args = _parse_args(settings.mcp_server_args)
    env = os.environ.copy()
    if settings.mcp_database_url:
        env["DATABASE_URL"] = settings.mcp_database_url
    if settings.mcp_allow_write_ops:
        env["DANGEROUSLY_ALLOW_WRITE_OPS"] = "true"
    return {
        "transport": "stdio",
        "command": settings.mcp_server_command,
        "args": args,
        "env": env,
    }
