"""Database read/write query stubs for all tables."""

from typing import Any


# --------------- sessions ---------------

def create_session() -> int:
    """Insert a new session row and return the session_id.

    Returns
    -------
    int
        The auto-generated session_id.
    """
    # TODO: INSERT INTO sessions DEFAULT VALUES RETURNING session_id
    pass


# --------------- messages ---------------

def save_message(session_id: int, role: str, content: str) -> int:
    """Persist a chat message.

    Parameters
    ----------
    session_id : int
    role : str
        One of 'user', 'assistant', 'system'.
    content : str

    Returns
    -------
    int
        The auto-generated message id.
    """
    # TODO: INSERT INTO messages (session_id, role, content) VALUES ...
    pass


def get_messages(session_id: int) -> list[dict[str, Any]]:
    """Retrieve all messages for a session, ordered by created_at.

    Parameters
    ----------
    session_id : int

    Returns
    -------
    list[dict]
        Each dict has keys: id, role, content, created_at.
    """
    # TODO: SELECT * FROM messages WHERE session_id = %s ORDER BY created_at
    pass


# --------------- topics ---------------

def upsert_topic(name: str, tags: list[str] | None = None) -> int:
    """Insert a topic or return existing topic_id.

    Parameters
    ----------
    name : str
    tags : list[str] | None

    Returns
    -------
    int
        The topic_id.
    """
    # TODO: INSERT ... ON CONFLICT (name) DO UPDATE SET tags = EXCLUDED.tags RETURNING topic_id
    pass


# --------------- study_plan & plan_items ---------------

def create_plan(title: str) -> int:
    """Create a new study plan.

    Returns
    -------
    int
        The plan_id.
    """
    # TODO: INSERT INTO study_plan (title) VALUES ... RETURNING plan_id
    pass


def add_plan_item(plan_id: int, title: str, topic_id: int | None = None,
                  due_date: str | None = None, notes: str | None = None) -> int:
    """Add an item to an existing study plan.

    Returns
    -------
    int
        The item_id.
    """
    # TODO: INSERT INTO plan_items ...
    pass


def update_plan_item_status(item_id: int, status: str) -> None:
    """Update a plan item's status ('pending' | 'in_progress' | 'done').

    Parameters
    ----------
    item_id : int
    status : str
    """
    # TODO: UPDATE plan_items SET status = %s WHERE item_id = %s
    pass


def get_plan_items(plan_id: int) -> list[dict[str, Any]]:
    """Fetch all items for a study plan.

    Returns
    -------
    list[dict]
    """
    # TODO: SELECT * FROM plan_items WHERE plan_id = %s ORDER BY item_id
    pass


# --------------- quiz_attempts ---------------

def save_quiz_attempt(topic_id: int | None, question: str,
                      user_answer: str | None, score: float | None,
                      feedback: str | None) -> int:
    """Record a quiz attempt.

    Returns
    -------
    int
        The attempt_id.
    """
    # TODO: INSERT INTO quiz_attempts ...
    pass


def get_weak_topics(limit: int = 5) -> list[dict[str, Any]]:
    """Return topics with lowest average quiz scores.

    Parameters
    ----------
    limit : int

    Returns
    -------
    list[dict]
        Each dict has keys: topic_id, name, avg_score.
    """
    # TODO: SELECT topic_id, AVG(score) ... GROUP BY topic_id ORDER BY avg_score LIMIT %s
    pass


# --------------- flashcards ---------------

def create_flashcard(topic_id: int | None, front: str, back: str) -> int:
    """Create a new flashcard.

    Returns
    -------
    int
        The card_id.
    """
    # TODO: INSERT INTO flashcards (topic_id, front, back) VALUES ...
    pass


def get_due_flashcards(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch flashcards due for review.

    Parameters
    ----------
    limit : int

    Returns
    -------
    list[dict]
    """
    # TODO: SELECT * FROM flashcards WHERE next_review_at <= NOW() ORDER BY next_review_at LIMIT %s
    pass


def update_flashcard_review(card_id: int, ease_factor: float,
                            next_review_at: str) -> None:
    """Update a flashcard after review.

    Parameters
    ----------
    card_id : int
    ease_factor : float
    next_review_at : str
        ISO-format timestamp.
    """
    # TODO: UPDATE flashcards SET last_seen = NOW(), ease_factor = %s, next_review_at = %s WHERE card_id = %s
    pass
