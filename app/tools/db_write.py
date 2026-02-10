"""PostgreSQL write tool node."""

import asyncio
import logging
import os

from app.config import settings
from app.models.state import GraphState
from app.db.repository_factory import get_repository, get_psycopg_repository

logger = logging.getLogger(__name__)


def _persist(repo, state: GraphState) -> None:
    intent = state.get("intent")
    session_id = state.get("session_id")
    specialist_output = state.get("specialist_output")
    plan_draft = state.get("plan_draft")
    plan_confirmed = state.get("plan_confirmed")

    # Minimal safe persistence until specialists are fully implemented.
    if session_id is not None and specialist_output:
        repo.save_message(session_id, "assistant", specialist_output)

    if intent == "PLAN" and plan_confirmed and plan_draft:
        title = plan_draft.get("title", "Study Plan")
        plan_id = repo.create_plan(title)
        items = plan_draft.get("items") or []
        for item in items:
            topic_id = None
            topic_name = item.get("topic") if isinstance(item, dict) else None
            if topic_name:
                topic_id = repo.upsert_topic(topic_name)
            repo.add_plan_item(
                plan_id=plan_id,
                title=item.get("title", "Plan item"),
                topic_id=topic_id,
                due_date=item.get("due_date"),
                notes=item.get("notes"),
            )
        return


def db_write_node(state: GraphState) -> dict:
    """Persist specialist output to PostgreSQL based on intent."""
    if settings.db_backend.lower() == "mcp":
        _persist_async(state)
        return {}

    repo = get_repository()
    try:
        _persist(repo, state)
    except Exception:
        if settings.mcp_fallback_to_psycopg2:
            logger.warning("MCP DB write failed, falling back to psycopg2", exc_info=True)
            _persist(get_psycopg_repository(), state)
        else:
            raise

    return {}


def _persist_async(state: GraphState) -> None:
    asyncio.run(_persist_async_inner(state))


async def _persist_async_inner(state: GraphState) -> None:
    from app.mcp.manager import _parse_args
    from app.db.mcp_repository import _inline_params, _extract_rows
    from app.mcp.client import extract_payload
    from langchain_mcp_adapters import client as mcp_client

    intent = state.get("intent")
    session_id = state.get("session_id")
    specialist_output = state.get("specialist_output")
    plan_draft = state.get("plan_draft")
    plan_confirmed = state.get("plan_confirmed")

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

        if session_id is not None:
            await _call(
                "INSERT INTO sessions (session_id) VALUES (%s) ON CONFLICT DO NOTHING",
                [session_id],
            )

        if session_id is not None and specialist_output:
            await _call(
                "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s)",
                [session_id, "assistant", specialist_output],
            )

        if intent == "PLAN" and plan_confirmed and plan_draft:
            title = plan_draft.get("title", "Study Plan")
            plan_payload = await _call(
                "INSERT INTO study_plan (title) VALUES (%s) RETURNING plan_id",
                [title],
            )
            plan_rows = _extract_rows(plan_payload)
            plan_id = plan_rows[0]["plan_id"] if plan_rows else None

            items = plan_draft.get("items") or []
            for item in items:
                topic_id = None
                topic_name = item.get("topic") if isinstance(item, dict) else None
                if topic_name:
                    topic_payload = await _call(
                        "INSERT INTO topics (name, tags) VALUES (%s, %s) "
                        "ON CONFLICT (name) DO UPDATE SET tags = EXCLUDED.tags "
                        "RETURNING topic_id",
                        [topic_name, None],
                    )
                    topic_rows = _extract_rows(topic_payload)
                    if topic_rows:
                        topic_id = topic_rows[0]["topic_id"]
                await _call(
                    "INSERT INTO plan_items (plan_id, topic_id, title, due_date, notes) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    [
                        plan_id,
                        topic_id,
                        item.get("title", "Plan item"),
                        item.get("due_date"),
                        item.get("notes"),
                    ],
                )


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
