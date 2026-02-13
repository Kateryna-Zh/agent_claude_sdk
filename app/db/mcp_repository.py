"""MCP-backed PostgreSQL repository."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from app.config import settings

from app.mcp.client import MCPClient


class MCPRepository:
    """Repository implementation backed by MCP server calls."""

    def __init__(self, client: MCPClient) -> None:
        self._client = client

    def create_session(self) -> int | None:
        rows = self._fetch_one(
            "INSERT INTO sessions DEFAULT VALUES RETURNING session_id"
        )
        return int(rows["session_id"]) if rows else None

    def save_message(self, session_id: int, role: str, content: str) -> int | None:
        rows = self._fetch_one(
            "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s) "
            "RETURNING id",
            [session_id, role, content],
        )
        return int(rows["id"]) if rows else None

    def get_messages(self, session_id: int) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT id, role, content, created_at "
            "FROM messages WHERE session_id = %s ORDER BY created_at",
            [session_id],
        )

    def upsert_topic(self, name: str, tags: list[str] | None = None) -> int | None:
        rows = self._fetch_one(
            "INSERT INTO topics (name, tags) VALUES (%s, %s) "
            "ON CONFLICT (name) DO UPDATE SET tags = EXCLUDED.tags "
            "RETURNING topic_id",
            [name, tags],
        )
        return int(rows["topic_id"]) if rows else None

    def create_plan(self, title: str) -> int | None:
        rows = self._fetch_one(
            "INSERT INTO study_plan (title) VALUES (%s) RETURNING plan_id",
            [title],
        )
        return int(rows["plan_id"]) if rows else None

    def add_plan_item(
        self,
        plan_id: int,
        title: str,
        topic_id: int | None = None,
        due_date: str | None = None,
        notes: str | None = None,
    ) -> int | None:
        rows = self._fetch_one(
            "INSERT INTO plan_items (plan_id, topic_id, title, due_date, notes) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING item_id",
            [plan_id, topic_id, title, due_date, notes],
        )
        return int(rows["item_id"]) if rows else None

    def update_plan_item_status(self, item_id: int, status: str) -> None:
        self._execute(
            "UPDATE plan_items SET status = %s WHERE item_id = %s",
            [status, item_id],
        )

    def get_plan_items(self, plan_id: int) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT item_id, plan_id, topic_id, title, status, due_date, notes "
            "FROM plan_items WHERE plan_id = %s ORDER BY item_id",
            [plan_id],
        )

    def save_quiz_attempt(
        self,
        topic_id: int | None,
        question: str,
        user_answer: str | None,
        score: float | None,
        feedback: str | None,
    ) -> int | None:
        rows = self._fetch_one(
            "INSERT INTO quiz_attempts (topic_id, question, user_answer, score, feedback) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING attempt_id",
            [topic_id, question, user_answer, score, feedback],
        )
        return int(rows["attempt_id"]) if rows else None

    def get_weak_topics(self, limit: int = 5) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT t.topic_id, t.name, AVG(q.score) AS avg_score "
            "FROM topics t JOIN quiz_attempts q ON q.topic_id = t.topic_id "
            "GROUP BY t.topic_id, t.name "
            "ORDER BY avg_score ASC NULLS LAST LIMIT %s",
            [limit],
        )

    def create_flashcard(self, topic_id: int | None, front: str, back: str) -> int | None:
        rows = self._fetch_one(
            "INSERT INTO flashcards (topic_id, front, back) VALUES (%s, %s, %s) "
            "RETURNING card_id",
            [topic_id, front, back],
        )
        return int(rows["card_id"]) if rows else None

    def get_due_flashcards(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT card_id, topic_id, front, back, last_seen, ease_factor, next_review_at "
            "FROM flashcards "
            "WHERE next_review_at IS NULL OR next_review_at <= NOW() "
            "ORDER BY next_review_at NULLS FIRST LIMIT %s",
            [limit],
        )

    def update_flashcard_review(
        self, card_id: int, ease_factor: float | None, next_review_at: str | None
    ) -> None:
        self._execute(
            "UPDATE flashcards SET last_seen = NOW(), "
            "ease_factor = COALESCE(%s, ease_factor), "
            "next_review_at = COALESCE(%s, next_review_at) "
            "WHERE card_id = %s",
            [ease_factor, next_review_at, card_id],
        )

    def get_latest_plan_id(self) -> int | None:
        rows = self._fetch_one(
            "SELECT plan_id FROM study_plan ORDER BY created_at DESC LIMIT 1"
        )
        return int(rows["plan_id"]) if rows else None

    def get_plans(self) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT plan_id, title, created_at FROM study_plan ORDER BY created_at DESC"
        )
    
    def get_wrong_questions(self, topic_id: int) -> list[dict]:
         return self._fetch_all(
             "SELECT attempt_id, question FROM quiz_attempts WHERE topic_id = %s",
             [topic_id],
         )

    def delete_quiz_attempt(self, attempt_id: int) -> None:
        self._execute(
            "DELETE FROM quiz_attempts WHERE attempt_id = %s",
            [attempt_id],
        )

    def _execute(self, sql: str, params: list[Any] | None = None) -> Any:
        params = params or []
        if params and not settings.mcp_supports_params:
            sql = _inline_params(sql, params)
            params = []
        else:
            sql = _to_dollar_params(sql)
        return self._client.query(sql, params)

    def _fetch_all(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        payload = self._execute(sql, params)
        rows = _extract_rows(payload)
        return rows

    def _fetch_one(self, sql: str, params: list[Any] | None = None) -> dict[str, Any] | None:
        rows = self._fetch_all(sql, params)
        return rows[0] if rows else None


def _to_dollar_params(sql: str) -> str:
    parts = sql.split("%s")
    if len(parts) == 1:
        return sql
    converted: list[str] = []
    for idx, part in enumerate(parts[:-1], start=1):
        converted.append(part)
        converted.append(f"${idx}")
    converted.append(parts[-1])
    return "".join(converted)


def _inline_params(sql: str, params: list[Any]) -> str:
    parts = sql.split("%s")
    if len(parts) == 1:
        return sql
    if len(parts) - 1 != len(params):
        raise ValueError("Parameter count does not match placeholders")
    out: list[str] = []
    for idx, part in enumerate(parts[:-1]):
        out.append(part)
        out.append(_literal(params[idx]))
    out.append(parts[-1])
    return "".join(out)


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return f"'{value.isoformat()}'"
    if isinstance(value, (list, tuple)):
        inner = ", ".join(_literal(item) for item in value)
        return f"ARRAY[{inner}]"
    if isinstance(value, dict):
        payload = json.dumps(value)
        return "'" + payload.replace("'", "''") + "'"
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "result", "results"):
            if key in payload and isinstance(payload[key], list):
                return [row for row in payload[key] if isinstance(row, dict)]
        if "row" in payload and isinstance(payload["row"], dict):
            return [payload["row"]]
    return []
