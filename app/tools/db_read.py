"""PostgreSQL read tool node."""

import logging

from app.config import settings
from app.models.state import GraphState
from app.db.repository_factory import get_repository, get_psycopg_repository

logger = logging.getLogger(__name__)


def _fetch(repo, state: GraphState) -> dict:
    intent = state.get("intent")
    session_id = state.get("session_id")

    data: dict = {}

    if intent in {"QUIZ", "REVIEW"}:
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
    repo = get_repository()
    try:
        return _fetch(repo, state)
    except Exception:
        if settings.mcp_fallback_to_psycopg2:
            logger.warning("MCP DB read failed, falling back to psycopg2", exc_info=True)
            return _fetch(get_psycopg_repository(), state)
        raise
