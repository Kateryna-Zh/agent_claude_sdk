"""DB tool definitions and executors for tool-calling agents."""

from __future__ import annotations

from typing import Any

from app.db.repository_factory import get_repository


def execute_tool(
    name: str,
    args: dict[str, Any],
    db_context: dict[str, Any],
    repo=None,
) -> dict[str, Any]:
    repo = repo or get_repository()
    if name == "list_plans":
        plans = repo.get_plans()
        db_context["plans"] = plans
        return {"plans": plans}
    if name == "list_plan_items":
        plan_id = args.get("plan_id")
        plan_title = args.get("plan_title")
        result = _list_plan_items(repo, db_context, plan_id, plan_title)
        return result
    if name == "write_plan":
        title = args.get("title") or "Study Plan"
        items = args.get("items") or []
        plan_id = repo.create_plan(title)
        for item in items:
            repo.add_plan_item(
                plan_id=plan_id,
                title=item.get("title", "Plan item"),
                topic_id=None,
                due_date=item.get("due_date") or None,
                notes=item.get("notes") or None,
            )
        db_context["created_plan_id"] = plan_id
        return {"created_plan_id": plan_id}
    if name == "add_plan_item":
        plan_id = args.get("plan_id")
        if plan_id == "latest":
            plan_id = repo.get_latest_plan_id()
        item_id = repo.add_plan_item(
            plan_id=plan_id,
            title=args.get("title", "Plan item"),
            topic_id=None,
            due_date=args.get("due_date") or None,
            notes=args.get("notes") or None,
        )
        return {"item_id": item_id}
    if name == "update_item_status":
        item_id = _resolve_item_id_from_args(repo, db_context, args)
        if item_id is not None:
            repo.update_plan_item_status(item_id, args.get("status", "in_progress"))
            return {"item_id": item_id, "status": args.get("status")}
        return {"error": "item_not_found"}
    if name == "update_plan_status":
        plan_id = _resolve_plan_id_from_args(repo, db_context, args)
        if plan_id is not None:
            for item in repo.get_plan_items(plan_id):
                repo.update_plan_item_status(item["item_id"], args.get("status", "in_progress"))
            return {"plan_id": plan_id, "status": args.get("status")}
        return {"error": "plan_not_found"}
    if name == "save_quiz_attempt":
        attempt_id = repo.save_quiz_attempt(
            topic_id=args.get("topic_id"),
            question=args.get("question", ""),
            user_answer=args.get("user_answer"),
            score=args.get("score"),
            feedback=args.get("feedback"),
        )
        return {"attempt_id": attempt_id}
    if name == "get_weak_topics":
        limit = args.get("limit", 5)
        topics = repo.get_weak_topics(limit)
        db_context["weak_topics"] = topics
        return {"weak_topics": topics}
    if name == "get_due_flashcards":
        limit = args.get("limit", 10)
        cards = repo.get_due_flashcards(limit)
        db_context["due_flashcards"] = cards
        return {"due_flashcards": cards}
    if name == "create_flashcard":
        card_id = repo.create_flashcard(
            topic_id=args.get("topic_id"),
            front=args.get("front", ""),
            back=args.get("back", ""),
        )
        return {"card_id": card_id}
    if name == "update_flashcard_review":
        repo.update_flashcard_review(
            card_id=args["card_id"],
            ease_factor=args.get("ease_factor", 2.5),
            next_review_at=args.get("next_review_at", ""),
        )
        return {"card_id": args["card_id"]}
    if name == "get_messages":
        session_id = args.get("session_id")
        messages = repo.get_messages(session_id)
        db_context["messages"] = messages
        return {"messages": messages}
    if name == "save_message":
        msg_id = repo.save_message(
            session_id=args["session_id"],
            role=args.get("role", "assistant"),
            content=args.get("content", ""),
        )
        return {"message_id": msg_id}
    return {"error": "unknown_tool"}


def _list_plan_items(repo, db_context: dict[str, Any], plan_id: Any, plan_title: str | None) -> dict[str, Any]:
    plans = db_context.get("plans") or repo.get_plans()
    db_context["plans"] = plans
    if plan_id == "latest":
        plan_id = repo.get_latest_plan_id()
    if plan_id is None and plan_title:
        candidate_ids = _resolve_plan_ids(plans, plan_title)
        if candidate_ids:
            db_context["requested_plan_title"] = plan_title
        found_any = False
        for candidate_id in candidate_ids:
            items = repo.get_plan_items(candidate_id)
            if items:
                db_context.setdefault("plan_items", {})[candidate_id] = items
                db_context["requested_plan_id"] = candidate_id
                found_any = True
        if found_any:
            return {"plan_items": db_context.get("plan_items", {})}
        if candidate_ids:
            items = repo.get_plan_items(candidate_ids[0])
            db_context.setdefault("plan_items", {})[candidate_ids[0]] = items
            db_context["requested_plan_id"] = candidate_ids[0]
            return {"plan_items": db_context.get("plan_items", {})}
    if plan_id is not None:
        items = repo.get_plan_items(plan_id)
        db_context.setdefault("plan_items", {})[plan_id] = items
        db_context["requested_plan_id"] = plan_id
        return {"plan_items": db_context.get("plan_items", {})}
    return {"plan_items": {}}


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


def _resolve_plan_id_from_args(repo, db_context: dict[str, Any], args: dict[str, Any]) -> int | None:
    plan_id = args.get("plan_id")
    plan_title = args.get("plan_title")
    if plan_id == "latest":
        return repo.get_latest_plan_id()
    if plan_id is None and plan_title:
        plans = db_context.get("plans") or repo.get_plans()
        db_context["plans"] = plans
        candidate_ids = _resolve_plan_ids(plans, plan_title)
        return candidate_ids[0] if candidate_ids else None
    return plan_id


def _resolve_item_id_from_args(repo, db_context: dict[str, Any], args: dict[str, Any]) -> int | None:
    item_id = args.get("item_id")
    if item_id is not None:
        return item_id
    plan_id = _resolve_plan_id_from_args(repo, db_context, args)
    if plan_id is None:
        return None
    items = repo.get_plan_items(plan_id)
    item_title = (args.get("item_title") or "").lower()
    for item in items:
        title = str(item.get("title", "")).lower()
        if title == item_title:
            return item.get("item_id")
    for item in items:
        title = str(item.get("title", "")).lower()
        if item_title and item_title in title:
            return item.get("item_id")
    return None


def get_langchain_tools(db_context: dict[str, Any], repo=None):
    from langchain_core.tools import StructuredTool

    repo = repo or get_repository()

    def list_plans() -> dict[str, Any]:
        """List all study plans."""
        return execute_tool("list_plans", {}, db_context, repo=repo)

    def list_plan_items(plan_id: int | str | None = None, plan_title: str | None = None) -> dict[str, Any]:
        """List items for a study plan by ID or title."""
        return execute_tool(
            "list_plan_items",
            {"plan_id": plan_id, "plan_title": plan_title},
            db_context,
            repo=repo,
        )

    def write_plan(title: str, items: list[dict[str, Any]]):
        """Create a new study plan with items."""
        return execute_tool("write_plan", {"title": title, "items": items}, db_context, repo=repo)

    def add_plan_item(
        plan_id: int | str,
        title: str,
        topic: str | None = None,
        due_date: str | None = None,
        notes: str | None = None,
    ):
        """Add an item to an existing study plan."""
        return execute_tool(
            "add_plan_item",
            {"plan_id": plan_id, "title": title, "topic": topic, "due_date": due_date, "notes": notes},
            db_context,
            repo=repo,
        )

    def update_item_status(
        status: str,
        item_id: int | None = None,
        item_title: str | None = None,
        plan_id: int | str | None = None,
        plan_title: str | None = None,
    ):
        """Update a plan item status (pending, in_progress, done)."""
        return execute_tool(
            "update_item_status",
            {
                "status": status,
                "item_id": item_id,
                "item_title": item_title,
                "plan_id": plan_id,
                "plan_title": plan_title,
            },
            db_context,
            repo=repo,
        )

    def update_plan_status(
        status: str,
        plan_id: int | str | None = None,
        plan_title: str | None = None,
    ):
        """Update all items in a plan to the given status."""
        return execute_tool(
            "update_plan_status",
            {"status": status, "plan_id": plan_id, "plan_title": plan_title},
            db_context,
            repo=repo,
        )

    def save_quiz_attempt(
        question: str,
        topic_id: int | None = None,
        user_answer: str | None = None,
        score: float | None = None,
        feedback: str | None = None,
    ):
        """Record a quiz attempt with question, answer, score, and feedback."""
        return execute_tool(
            "save_quiz_attempt",
            {"topic_id": topic_id, "question": question, "user_answer": user_answer, "score": score, "feedback": feedback},
            db_context,
            repo=repo,
        )

    def get_weak_topics(limit: int = 5):
        """Get topics with the lowest average quiz scores."""
        return execute_tool("get_weak_topics", {"limit": limit}, db_context, repo=repo)

    def get_due_flashcards(limit: int = 10):
        """Get flashcards due for review."""
        return execute_tool("get_due_flashcards", {"limit": limit}, db_context, repo=repo)

    def create_flashcard(front: str, back: str, topic_id: int | None = None):
        """Create a new flashcard with front and back text."""
        return execute_tool(
            "create_flashcard",
            {"topic_id": topic_id, "front": front, "back": back},
            db_context,
            repo=repo,
        )

    def update_flashcard_review(card_id: int, ease_factor: float = 2.5, next_review_at: str = ""):
        """Update a flashcard after review with new ease factor and next review date."""
        return execute_tool(
            "update_flashcard_review",
            {"card_id": card_id, "ease_factor": ease_factor, "next_review_at": next_review_at},
            db_context,
            repo=repo,
        )

    def get_messages(session_id: int):
        """Retrieve all messages for a chat session."""
        return execute_tool("get_messages", {"session_id": session_id}, db_context, repo=repo)

    def save_message(session_id: int, role: str, content: str):
        """Save a chat message (role: user, assistant, or system)."""
        return execute_tool(
            "save_message",
            {"session_id": session_id, "role": role, "content": content},
            db_context,
            repo=repo,
        )

    return [
        StructuredTool.from_function(list_plans, name="list_plans"),
        StructuredTool.from_function(list_plan_items, name="list_plan_items"),
        StructuredTool.from_function(write_plan, name="write_plan"),
        StructuredTool.from_function(add_plan_item, name="add_plan_item"),
        StructuredTool.from_function(update_item_status, name="update_item_status"),
        StructuredTool.from_function(update_plan_status, name="update_plan_status"),
        StructuredTool.from_function(save_quiz_attempt, name="save_quiz_attempt"),
        StructuredTool.from_function(get_weak_topics, name="get_weak_topics"),
        StructuredTool.from_function(get_due_flashcards, name="get_due_flashcards"),
        StructuredTool.from_function(create_flashcard, name="create_flashcard"),
        StructuredTool.from_function(update_flashcard_review, name="update_flashcard_review"),
        StructuredTool.from_function(get_messages, name="get_messages"),
        StructuredTool.from_function(save_message, name="save_message"),
    ]
