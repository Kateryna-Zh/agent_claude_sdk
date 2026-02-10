"""Repository backend selection with MCP fallback."""

from __future__ import annotations

import logging

from app.config import settings
from app.db import repository as psycopg_repo
from app.db.mcp_repository import MCPRepository
from app.mcp.manager import mcp_manager

logger = logging.getLogger(__name__)


class PsycopgRepository:
    """Adapter to expose psycopg2 module functions as an object."""

    def create_session(self) -> int:
        return psycopg_repo.create_session()

    def save_message(self, session_id: int, role: str, content: str) -> int:
        return psycopg_repo.save_message(session_id, role, content)

    def get_messages(self, session_id: int):
        return psycopg_repo.get_messages(session_id)

    def upsert_topic(self, name: str, tags=None) -> int:
        return psycopg_repo.upsert_topic(name, tags)

    def create_plan(self, title: str) -> int:
        return psycopg_repo.create_plan(title)

    def add_plan_item(self, plan_id: int, title: str, topic_id=None, due_date=None, notes=None) -> int:
        return psycopg_repo.add_plan_item(plan_id, title, topic_id, due_date, notes)

    def update_plan_item_status(self, item_id: int, status: str) -> None:
        return psycopg_repo.update_plan_item_status(item_id, status)

    def get_plan_items(self, plan_id: int):
        return psycopg_repo.get_plan_items(plan_id)

    def get_latest_plan_id(self):
        return psycopg_repo.get_latest_plan_id()

    def get_plans(self):
        return psycopg_repo.get_plans()

    def save_quiz_attempt(self, topic_id, question, user_answer, score, feedback) -> int:
        return psycopg_repo.save_quiz_attempt(topic_id, question, user_answer, score, feedback)

    def get_weak_topics(self, limit: int = 5):
        return psycopg_repo.get_weak_topics(limit)

    def create_flashcard(self, topic_id, front: str, back: str) -> int:
        return psycopg_repo.create_flashcard(topic_id, front, back)

    def get_due_flashcards(self, limit: int = 10):
        return psycopg_repo.get_due_flashcards(limit)

    def update_flashcard_review(self, card_id: int, ease_factor: float, next_review_at: str) -> None:
        return psycopg_repo.update_flashcard_review(card_id, ease_factor, next_review_at)


_psycopg_repo = PsycopgRepository()


def get_repository():
    if settings.db_backend.lower() != "mcp":
        return _psycopg_repo

    client = mcp_manager.get_client()
    if client is None:
        if settings.mcp_fallback_to_psycopg2:
            logger.warning("MCP DB unavailable, falling back to psycopg2")
            return _psycopg_repo
        raise RuntimeError("MCP DB requested but client not available")

    return MCPRepository(client)


def get_psycopg_repository() -> PsycopgRepository:
    return _psycopg_repo
