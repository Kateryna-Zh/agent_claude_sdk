"""PostgreSQL write tool node."""

import logging

from app.config import settings
from app.models.state import GraphState
from app.db.repository_factory import get_repository, get_psycopg_repository

logger = logging.getLogger(__name__)


def _persist(repo, state: GraphState) -> None:
    intent = state.get("intent")
    session_id = state.get("session_id")
    specialist_output = state.get("specialist_output")

    # Minimal safe persistence until specialists are fully implemented.
    if session_id is not None and specialist_output:
        repo.save_message(session_id, "assistant", specialist_output)

    # TODO: Implement structured writes when specialist outputs are defined.
    # - PLAN -> create_plan() + add_plan_item()
    # - QUIZ -> save_quiz_attempt()
    # - LOG_PROGRESS -> update_plan_item_status()
    _ = intent


def db_write_node(state: GraphState) -> dict:
    """Persist specialist output to PostgreSQL based on intent."""
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
