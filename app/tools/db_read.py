"""PostgreSQL read tool node."""

import asyncio
import logging
import os

from app.config import settings
from app.models.state import GraphState
from app.db.repository_factory import get_repository, get_psycopg_repository

logger = logging.getLogger(__name__)


def _fetch(repo, state: GraphState) -> dict:
    intent = state.get("intent")
    session_id = state.get("session_id")

    data: dict = {}

    if intent == "REVIEW":
        plans = repo.get_plans()
        data["plans"] = plans
        plan_items = {}
        for plan in plans:
            plan_id = plan.get("plan_id")
            if plan_id is not None:
                plan_items[plan_id] = repo.get_plan_items(plan_id)
        data["plan_items"] = plan_items
    elif intent == "QUIZ":
        data["weak_topics"] = repo.get_weak_topics()
        data["due_flashcards"] = repo.get_due_flashcards()
    elif intent in {"PLAN", "LOG_PROGRESS"}:
        plan_id = repo.get_latest_plan_id()
        if plan_id is not None:
            data["plan_id"] = plan_id
            data["plan_items"] = repo.get_plan_items(plan_id)
    elif session_id is not None:
        data["messages"] = repo.get_messages(session_id)

    return {"db_context": data}


def db_read_node(state: GraphState) -> dict:
    """Read relevant data from PostgreSQL based on intent.

    Populates: db_context.
    """
    if settings.db_backend.lower() == "mcp":
        return _fetch_mcp(state)

    repo = get_repository()
    try:
        return _fetch(repo, state)
    except Exception:
        if settings.mcp_fallback_to_psycopg2:
            logger.warning("MCP DB read failed, falling back to psycopg2", exc_info=True)
            return _fetch(get_psycopg_repository(), state)
        raise


def _fetch_mcp(state: GraphState) -> dict:
    return asyncio.run(_fetch_mcp_inner(state))


async def _fetch_mcp_inner(state: GraphState) -> dict:
    from app.mcp.manager import _parse_args
    from app.db.mcp_repository import _inline_params, _extract_rows
    from app.mcp.client import extract_payload
    from langchain_mcp_adapters import client as mcp_client

    intent = state.get("intent")
    session_id = state.get("session_id")

    connection = _build_mcp_connection(_parse_args)

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
            return extract_payload(result)

        data: dict = {}

        if intent == "REVIEW":
            payload = await _call(
                "SELECT plan_id, title, created_at FROM study_plan ORDER BY created_at DESC"
            )
            plans = _extract_rows(payload)
            data["plans"] = plans
            items_payload = await _call(
                "SELECT item_id, plan_id, topic_id, title, status, due_date, notes "
                "FROM plan_items ORDER BY plan_id, item_id"
            )
            items = _extract_rows(items_payload)
            grouped = {}
            for item in items:
                plan_id = item.get("plan_id")
                if plan_id is None:
                    continue
                grouped.setdefault(plan_id, []).append(item)
            data["plan_items"] = grouped
        elif intent == "QUIZ":
            weak_payload = await _call(
                "SELECT t.topic_id, t.name, AVG(q.score) AS avg_score "
                "FROM topics t JOIN quiz_attempts q ON q.topic_id = t.topic_id "
                "GROUP BY t.topic_id, t.name "
                "ORDER BY avg_score ASC NULLS LAST LIMIT %s",
                [5],
            )
            data["weak_topics"] = _extract_rows(weak_payload)
            due_payload = await _call(
                "SELECT card_id, topic_id, front, back, last_seen, ease_factor, next_review_at "
                "FROM flashcards WHERE next_review_at IS NULL OR next_review_at <= NOW() "
                "ORDER BY next_review_at NULLS FIRST LIMIT %s",
                [10],
            )
            data["due_flashcards"] = _extract_rows(due_payload)
        elif intent in {"PLAN", "LOG_PROGRESS"}:
            latest_payload = await _call(
                "SELECT plan_id FROM study_plan ORDER BY created_at DESC LIMIT 1"
            )
            latest_rows = _extract_rows(latest_payload)
            if latest_rows:
                plan_id = latest_rows[0].get("plan_id")
                data["plan_id"] = plan_id
                items_payload = await _call(
                    "SELECT item_id, plan_id, topic_id, title, status, due_date, notes "
                    "FROM plan_items WHERE plan_id = %s ORDER BY item_id",
                    [plan_id],
                )
                data["plan_items"] = _extract_rows(items_payload)
        elif session_id is not None:
            msg_payload = await _call(
                "SELECT id, role, content, created_at FROM messages WHERE session_id = %s ORDER BY created_at",
                [session_id],
            )
            data["messages"] = _extract_rows(msg_payload)

    return {"db_context": data}


def _build_mcp_connection(parse_args) -> dict:
    args = parse_args(settings.mcp_server_args)
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
