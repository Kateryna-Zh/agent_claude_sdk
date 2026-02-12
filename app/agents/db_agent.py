"""DB agent node — executes DB tools via tool-calling or intent fallback."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.models.state import GraphState
from app.llm.ollama_client import get_chat_model
from app.tools.db_tools import execute_tool, get_langchain_tools

logger = logging.getLogger("uvicorn.error")


def db_agent_node(state: GraphState) -> dict:
    """Execute DB actions using tool-calling or db_plan fallback."""
    db_context = state.get("db_context") or {}

    intent = state.get("intent")
    sub_intent = state.get("sub_intent")
    if intent == "REVIEW" and sub_intent in {"LIST_PLANS", "LIST_ITEMS"}:
        tool_calls = []
        if sub_intent == "LIST_PLANS":
            _reset_plan_item_context(db_context)
            tool_calls.append({"name": "list_plans", "arguments": {}})
        else:
            plan_title = db_context.get("requested_plan_title") or state.get("user_input")
            db_context["requested_plan_title"] = plan_title
            tool_calls.append({"name": "list_plans", "arguments": {}})
            tool_calls.append({"name": "list_plan_items", "arguments": {"plan_id": None, "plan_title": plan_title}})
        _execute_fallback_tools(state, db_context)
        logger.info(
            "DB agent fast-path tool_calls: %s",
            json.dumps({"tool_calls": tool_calls}, ensure_ascii=False),
        )
        response = _format_db_response(db_context)
        return {
            "user_response": response,
            "specialist_output": response,
            "db_context": db_context,
        }

    # Try tool-calling first (LangChain tools bound to the model).
    tool_result = _run_tool_calling(state, db_context)
    if tool_result is not None:
        # Check if a status update happened — return confirmation instead of plan listing.
        confirmation = _format_tool_result_confirmation(tool_result)
        if confirmation:
            return {
                "user_response": confirmation,
                "specialist_output": confirmation,
                "db_context": db_context,
            }
        response = _format_db_response(db_context)
        return {
            "user_response": response,
            "specialist_output": response,
            "db_context": db_context,
        }

    # Fallback to intent-driven tools if tool-calling returns nothing.
    _execute_fallback_tools(state, db_context)
    response = _format_db_response(db_context)
    return {
        "user_response": response,
        "specialist_output": response,
        "db_context": db_context,
    }



def _run_tool_calling(state: GraphState, db_context: dict[str, Any]) -> dict[str, Any] | None:
    if state.get("intent") == "PLAN" and state.get("sub_intent") != "SAVE_PLAN":
        return None
    tools = get_langchain_tools(db_context)
    system = (
        "You are a DB agent. Use tools to read/write the database. "
        "Prefer tools over free-form text. "
        "If intent is PLAN and sub_intent is SAVE_PLAN, call write_plan with plan_draft. "
        "If intent is REVIEW, call list_plans or list_plan_items as needed. "
        "If intent is LOG_PROGRESS, call update_item_status or update_plan_status. "
        "If no tool is needed, respond without tool_calls."
    )
    user_payload = {
        "user_input": state.get("user_input"),
        "intent": state.get("intent"),
        "sub_intent": state.get("sub_intent"),
        "plan_draft": state.get("plan_draft"),
        "db_context": db_context,
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload)},
    ]

    llm = get_chat_model().bind_tools(tools)
    try:
        response = llm.invoke(messages)
    except Exception as exc:
        logger.warning("DB agent tool-calling failed: %s", exc)
        return None

    tool_calls = getattr(response, "tool_calls", None) or []
    if not tool_calls:
        return None

    tool_map = {tool.name: tool for tool in tools}
    results = []
    for call in tool_calls:
        name = call.get("name")
        args = call.get("args") or {}
        if name == "write_plan":
            if not state.get("plan_confirmed"):
                logger.info("Skipping write_plan (plan not confirmed).")
                continue
            if not isinstance(args.get("items"), list):
                plan_draft = state.get("plan_draft") or {}
                args = {
                    "title": plan_draft.get("title") or args.get("title"),
                    "items": plan_draft.get("items") or [],
                }
                if not isinstance(args.get("items"), list):
                    logger.info("Skipping write_plan (invalid items payload).")
                    continue
        tool = tool_map.get(name)
        if tool is None:
            continue
        result = tool.invoke(args)
        results.append({"tool_call_id": call.get("id"), "name": name, "result": result})

    logger.info(
        "DB agent tool_calls: %s",
        json.dumps({"tool_calls": tool_calls, "results": results}, ensure_ascii=False),
    )

    return {"tool_calls": tool_calls, "results": results}


def _format_tool_result_confirmation(tool_result: dict[str, Any]) -> str | None:
    """If tool results contain a status update or write, return a confirmation message."""
    results = tool_result.get("results") or []
    confirmations = []
    for r in results:
        name = r.get("name", "")
        result = r.get("result") or {}
        if name == "update_item_status" and "error" not in result:
            item_id = result.get("item_id")
            status = result.get("status")
            confirmations.append(f"Status for item {item_id} updated to {status}.")
        elif name == "update_plan_status" and "error" not in result:
            plan_id = result.get("plan_id")
            status = result.get("status")
            confirmations.append(f"All items in plan {plan_id} updated to {status}.")
        elif name == "save_quiz_attempt" and "error" not in result:
            confirmations.append(f"Quiz attempt saved (attempt {result.get('attempt_id')}).")
        elif name == "create_flashcard" and "error" not in result:
            confirmations.append(f"Flashcard created (card {result.get('card_id')}).")
        elif name == "save_message" and "error" not in result:
            confirmations.append(f"Message saved.")
    return "\n".join(confirmations) if confirmations else None


def _execute_fallback_tools(state: GraphState, db_context: dict[str, Any]) -> None:
    intent = state.get("intent")
    sub_intent = state.get("sub_intent")
    if intent == "REVIEW" and sub_intent == "LIST_PLANS":
        _reset_plan_item_context(db_context)
        execute_tool("list_plans", {}, db_context)
        return
    if intent == "REVIEW" and sub_intent == "LIST_ITEMS":
        plan_title = db_context.get("requested_plan_title") or state.get("user_input")
        db_context["requested_plan_title"] = plan_title
        execute_tool("list_plans", {}, db_context)
        execute_tool("list_plan_items", {"plan_id": None, "plan_title": plan_title}, db_context)
        return
    if intent == "LOG_PROGRESS":
        item_title = db_context.get("requested_item_title")
        if item_title:
            result = execute_tool(
                "update_item_status",
                {"status": "in_progress", "item_title": item_title, "plan_id": "latest"},
                db_context,
            )
            if "error" not in result:
                db_context["_confirmation"] = f"Status for '{item_title}' updated to {result.get('status', 'in_progress')}."
            else:
                db_context["_confirmation"] = f"Could not find item '{item_title}'."
        return


def _format_db_response(db_context: dict[str, Any]) -> str:
    # If a confirmation was set by a write operation, return it directly.
    confirmation = db_context.pop("_confirmation", None)
    if confirmation:
        return confirmation

    plans = db_context.get("plans") or []
    items_map = db_context.get("plan_items") or {}
    requested_plan_id = db_context.get("requested_plan_id")
    requested_plan_title = db_context.get("requested_plan_title")
    requested_items = bool(db_context.get("requested_items"))

    if not plans and not items_map:
        return "Done."

    items_only = requested_items or bool(requested_plan_id or requested_plan_title)
    if items_only:
        matching_ids = []
        if requested_plan_title:
            matching_ids = _resolve_plan_ids(plans, requested_plan_title)
        if requested_plan_id and requested_plan_id not in matching_ids:
            matching_ids.append(requested_plan_id)
        if not matching_ids:
            return "Which plan do you want the items for?"
        lines = ["Here are the items for your plan(s):"]
        found_any = False
        for plan_id in matching_ids:
            items = items_map.get(plan_id, [])
            if not items:
                continue
            found_any = True
            created_at = _lookup_plan_created_at(plans, plan_id)
            header = f"Plan ID {plan_id}"
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

    lines = ["Here are your learning plans:"]
    seen_ids: set[int] = set()
    for plan in plans:
        plan_id = plan.get("plan_id")
        if plan_id in seen_ids:
            continue
        seen_ids.add(plan_id)
        lines.append(f"- {plan.get('title', 'Untitled plan')}")
    return "\n".join(lines)


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
        elif lowered in title or title in lowered:
            contains.append(plan_id)
    return exact + contains


def _lookup_plan_created_at(plans: list[dict[str, Any]], plan_id: int) -> str | None:
    for plan in plans:
        if plan.get("plan_id") == plan_id:
            return plan.get("created_at")
    return None


def _reset_plan_item_context(db_context: dict[str, Any]) -> None:
    db_context.pop("requested_plan_title", None)
    db_context.pop("requested_plan_id", None)
    db_context.pop("requested_items", None)
    db_context.pop("plan_items", None)
