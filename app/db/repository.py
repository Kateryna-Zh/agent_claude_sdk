"""Database read/write queries for all tables (psycopg2)."""

from __future__ import annotations

from typing import Any

from psycopg2.extras import RealDictCursor

from app.db.connection import get_connection, put_connection


def _execute(sql: str, params: list[Any] | None = None, *, fetch: str | None = None):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or [])
            if fetch == "one":
                row = cur.fetchone()
                conn.commit()
                return row
            if fetch == "all":
                rows = cur.fetchall()
                conn.commit()
                return rows
            conn.commit()
            return None
    except Exception:
        conn.rollback()
        raise
    finally:
        put_connection(conn)


# --------------- sessions ---------------

def create_session() -> int:
    """Insert a new session row and return the session_id."""
    row = _execute(
        "INSERT INTO sessions DEFAULT VALUES RETURNING session_id",
        fetch="one",
    )
    return int(row["session_id"])


# --------------- messages ---------------

def save_message(session_id: int, role: str, content: str) -> int:
    """Persist a chat message and return the message id."""
    row = _execute(
        "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s) RETURNING id",
        [session_id, role, content],
        fetch="one",
    )
    return int(row["id"])


def get_messages(session_id: int) -> list[dict[str, Any]]:
    """Retrieve all messages for a session, ordered by created_at."""
    return _execute(
        "SELECT id, role, content, created_at FROM messages WHERE session_id = %s ORDER BY created_at",
        [session_id],
        fetch="all",
    )


# --------------- topics ---------------

def upsert_topic(name: str, tags: list[str] | None = None) -> int:
    """Insert a topic or return existing topic_id."""
    row = _execute(
        "INSERT INTO topics (name, tags) VALUES (%s, %s) "
        "ON CONFLICT (name) DO UPDATE SET tags = EXCLUDED.tags RETURNING topic_id",
        [name, tags],
        fetch="one",
    )
    return int(row["topic_id"])


# --------------- study_plan & plan_items ---------------

def create_plan(title: str) -> int:
    """Create a new study plan."""
    row = _execute(
        "INSERT INTO study_plan (title) VALUES (%s) RETURNING plan_id",
        [title],
        fetch="one",
    )
    return int(row["plan_id"])


def add_plan_item(
    plan_id: int,
    title: str,
    topic_id: int | None = None,
    due_date: str | None = None,
    notes: str | None = None,
) -> int:
    """Add an item to an existing study plan."""
    row = _execute(
        "INSERT INTO plan_items (plan_id, topic_id, title, due_date, notes) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING item_id",
        [plan_id, topic_id, title, due_date, notes],
        fetch="one",
    )
    return int(row["item_id"])


def update_plan_item_status(item_id: int, status: str) -> None:
    """Update a plan item's status ('pending' | 'in_progress' | 'done')."""
    _execute(
        "UPDATE plan_items SET status = %s WHERE item_id = %s",
        [status, item_id],
    )


def get_plan_items(plan_id: int) -> list[dict[str, Any]]:
    """Fetch all items for a study plan."""
    return _execute(
        "SELECT item_id, plan_id, topic_id, title, status, due_date, notes "
        "FROM plan_items WHERE plan_id = %s ORDER BY item_id",
        [plan_id],
        fetch="all",
    )


def get_latest_plan_id() -> int | None:
    row = _execute(
        "SELECT plan_id FROM study_plan ORDER BY created_at DESC LIMIT 1",
        fetch="one",
    )
    return int(row["plan_id"]) if row else None


def get_plans() -> list[dict[str, Any]]:
    """Fetch all study plans."""
    return _execute(
        "SELECT plan_id, title, created_at FROM study_plan ORDER BY created_at DESC",
        fetch="all",
    )


# --------------- quiz_attempts ---------------

def save_quiz_attempt(
    topic_id: int | None,
    question: str,
    user_answer: str | None,
    score: float | None,
    feedback: str | None,
) -> int:
    """Record a quiz attempt."""
    row = _execute(
        "INSERT INTO quiz_attempts (topic_id, question, user_answer, score, feedback) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING attempt_id",
        [topic_id, question, user_answer, score, feedback],
        fetch="one",
    )
    return int(row["attempt_id"])


def get_weak_topics(limit: int = 5) -> list[dict[str, Any]]:
    """Return topics with lowest average quiz scores."""
    return _execute(
        "SELECT t.topic_id, t.name, AVG(q.score) AS avg_score "
        "FROM topics t JOIN quiz_attempts q ON q.topic_id = t.topic_id "
        "GROUP BY t.topic_id, t.name "
        "ORDER BY avg_score ASC NULLS LAST LIMIT %s",
        [limit],
        fetch="all",
    )


# --------------- flashcards ---------------

def create_flashcard(topic_id: int | None, front: str, back: str) -> int:
    """Create a new flashcard."""
    row = _execute(
        "INSERT INTO flashcards (topic_id, front, back) VALUES (%s, %s, %s) RETURNING card_id",
        [topic_id, front, back],
        fetch="one",
    )
    return int(row["card_id"])


def get_due_flashcards(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch flashcards due for review."""
    return _execute(
        "SELECT card_id, topic_id, front, back, last_seen, ease_factor, next_review_at "
        "FROM flashcards WHERE next_review_at IS NULL OR next_review_at <= NOW() "
        "ORDER BY next_review_at NULLS FIRST LIMIT %s",
        [limit],
        fetch="all",
    )


def update_flashcard_review(card_id: int, ease_factor: float, next_review_at: str) -> None:
    """Update a flashcard after review."""
    _execute(
        "UPDATE flashcards SET last_seen = NOW(), ease_factor = %s, next_review_at = %s "
        "WHERE card_id = %s",
        [ease_factor, next_review_at, card_id],
    )
