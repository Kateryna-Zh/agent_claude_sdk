"""DB tool definitions and executors for tool-calling agents."""

from __future__ import annotations

import json

from typing import Any, get_args, get_origin

from pydantic import BaseModel, ConfigDict, ValidationError

from app.db.repository_factory import get_repository
from app.tools import db_tool_models as m
from app.tools.contracts import ToolResult, err, ok
from app.tools.tool_registry import ToolSpec, get_tool, list_tools, register_tool


def _validation_error(exc: ValidationError) -> ToolResult:
    fields = []
    for e in exc.errors():
        loc = e.get("loc") or []
        field = ".".join(str(p) for p in loc) if loc else "__root__"
        fields.append({"field": field, "message": e.get("msg", "Invalid value")})
    return err("validation_error", "Invalid tool input", {"fields": fields})


def _not_found(entity_type: str, query: dict[str, Any]) -> ToolResult:
    return err(
        "not_found",
        f"{entity_type} not found",
        {"entity_type": entity_type, "query": query},
    )


def _db_error(exc: Exception) -> ToolResult:
    return err("db_error", "Database error", {"exception": str(exc)})


def _conflict(entity_type: str, candidates: list[dict[str, Any]]) -> ToolResult:
    return err(
        "conflict",
        f"Multiple {entity_type} matches found",
        {"entity_type": entity_type, "candidates": candidates},
    )


def _strip_extras(model: type[BaseModel], payload: Any) -> Any:
    """Recursively strip fields not declared in the Pydantic model.

    Walks nested ``BaseModel`` and ``list[BaseModel]`` fields so that only
    declared attributes survive at every level of the payload dict.
    """
    if not isinstance(payload, dict):
        return payload
    allowed = set(model.model_fields.keys())
    cleaned: dict[str, Any] = {k: v for k, v in payload.items() if k in allowed}
    for field_name, field_info in model.model_fields.items():
        if field_name not in cleaned:
            continue
        value = cleaned[field_name]
        annotation = field_info.annotation
        # Nested BaseModel — recurse into the dict value.
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if isinstance(value, dict):
                cleaned[field_name] = _strip_extras(annotation, value)
            continue
        # list[BaseModel] — recurse into each dict element.
        origin = get_origin(annotation)
        if origin is list:
            args = get_args(annotation)
            if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                if isinstance(value, list):
                    cleaned[field_name] = [
                        _strip_extras(args[0], item) if isinstance(item, dict) else item
                        for item in value
                    ]
    return cleaned


# --- Tool registration ---


def tool(name: str, model: type[m.BaseToolModel]):
    def _wrap(fn):
        register_tool(ToolSpec(name, model, fn))
        return fn

    return _wrap


# --- Tool handlers ---

@tool("list_plans", m.ListPlansInput)
def _list_plans(repo, db_context: dict[str, Any], _data: m.ListPlansInput) -> ToolResult:
    plans = repo.get_plans()
    db_context["plans"] = plans
    return ok({"plans": plans})


@tool("list_plan_items", m.ListPlanItemsInput)
def _list_plan_items(repo, db_context: dict[str, Any], data: m.ListPlanItemsInput) -> ToolResult:
    return _list_plan_items_impl(repo, db_context, data.plan_id, data.plan_title)


@tool("write_plan", m.WritePlanInput)
def _write_plan(repo, db_context: dict[str, Any], data: m.WritePlanInput) -> ToolResult:
    plan_id = repo.create_plan(data.title)
    for item in data.items:
        repo.add_plan_item(
            plan_id=plan_id,
            title=item.title,
            topic_id=None,
            due_date=item.due_date or None,
            notes=item.notes or None,
        )
    db_context["created_plan_id"] = plan_id
    return ok({"created_plan_id": plan_id})


@tool("add_plan_item", m.AddPlanItemInput)
def _add_plan_item(repo, _db_context: dict[str, Any], data: m.AddPlanItemInput) -> ToolResult:
    plan_id = data.plan_id
    if plan_id == "latest":
        plan_id = repo.get_latest_plan_id()
    if plan_id is None:
        return _not_found("plan", {"plan_id": "latest"})
    item_id = repo.add_plan_item(
        plan_id=plan_id,
        title=data.title,
        topic_id=None,
        due_date=data.due_date or None,
        notes=data.notes or None,
    )
    return ok({"item_id": item_id})


@tool("update_item_status", m.UpdateItemStatusInput)
def _update_item_status(repo, db_context: dict[str, Any], data: m.UpdateItemStatusInput) -> ToolResult:
    if data.item_id is not None:
        repo.update_plan_item_status(data.item_id, data.status)
        return ok({"item_id": data.item_id, "status": data.status})
    plan_id, plan_candidates = _resolve_plan_from_args(
        repo, db_context, data.plan_id, data.plan_title
    )
    if plan_candidates and plan_id is None:
        return _conflict("plan", plan_candidates)
    if plan_id is None:
        return _not_found(
            "plan",
            {"plan_id": data.plan_id, "plan_title": data.plan_title},
        )
    item_title = (data.item_title or "").strip()
    candidates = _find_item_candidates(repo, plan_id, item_title)
    if len(candidates) > 1:
        return _conflict("item", candidates)
    if not candidates:
        return _not_found(
            "item",
            {"item_title": data.item_title, "plan_id": plan_id},
        )
    item_id = candidates[0]["item_id"]
    repo.update_plan_item_status(item_id, data.status)
    return ok({"item_id": item_id, "status": data.status})


@tool("update_plan_status", m.UpdatePlanStatusInput)
def _update_plan_status(repo, db_context: dict[str, Any], data: m.UpdatePlanStatusInput) -> ToolResult:
    plan_id, candidates = _resolve_plan_from_args(repo, db_context, data.plan_id, data.plan_title)
    if candidates and plan_id is None:
        return _conflict("plan", candidates)
    if plan_id is not None:
        for item in repo.get_plan_items(plan_id):
            repo.update_plan_item_status(item["item_id"], data.status)
        return ok({"plan_id": plan_id, "status": data.status})
    return _not_found("plan", {"plan_id": data.plan_id, "plan_title": data.plan_title})


@tool("save_quiz_attempt", m.SaveQuizAttemptInput)
def _save_quiz_attempt(repo, _db_context: dict[str, Any], data: m.SaveQuizAttemptInput) -> ToolResult:
    attempt_id = repo.save_quiz_attempt(
        topic_id=data.topic_id,
        question=data.question,
        user_answer=data.user_answer,
        score=data.score,
        feedback=data.feedback,
    )
    return ok({"attempt_id": attempt_id})


@tool("get_wrong_questions", m.GetWrongQuestionsInput)
def _get_wrong_questions(repo, db_context: dict[str, Any], data: m.GetWrongQuestionsInput) -> ToolResult:
    questions = repo.get_wrong_questions(data.topic_id)
    db_context["wrong_questions"] = questions
    if not questions:
        return _not_found("topic", {"topic_id": data.topic_id})
    return ok({"wrong_questions": questions})


@tool("delete_quiz_attempt", m.DeleteQuizAttemptInput)
def _delete_quiz_attempt(repo, _db_context: dict[str, Any], data: m.DeleteQuizAttemptInput) -> ToolResult:
    repo.delete_quiz_attempt(data.attempt_id)
    return ok({"deleted_attempt_id": data.attempt_id})


@tool("get_weak_topics", m.GetWeakTopicsInput)
def _get_weak_topics(repo, db_context: dict[str, Any], data: m.GetWeakTopicsInput) -> ToolResult:
    topics = repo.get_weak_topics(data.limit)
    db_context["weak_topics"] = topics
    return ok({"weak_topics": topics})


@tool("get_due_flashcards", m.GetDueFlashcardsInput)
def _get_due_flashcards(repo, db_context: dict[str, Any], data: m.GetDueFlashcardsInput) -> ToolResult:
    cards = repo.get_due_flashcards(data.limit)
    db_context["due_flashcards"] = cards
    return ok({"due_flashcards": cards})


@tool("create_flashcard", m.CreateFlashcardInput)
def _create_flashcard(repo, _db_context: dict[str, Any], data: m.CreateFlashcardInput) -> ToolResult:
    card_id = repo.create_flashcard(
        topic_id=data.topic_id,
        front=data.front,
        back=data.back,
    )
    return ok({"card_id": card_id})


@tool("update_flashcard_review", m.UpdateFlashcardReviewInput)
def _update_flashcard_review(repo, _db_context: dict[str, Any], data: m.UpdateFlashcardReviewInput) -> ToolResult:
    repo.update_flashcard_review(
        card_id=data.card_id,
        ease_factor=data.ease_factor,
        next_review_at=data.next_review_at,
    )
    return ok({"card_id": data.card_id})


@tool("get_messages", m.GetMessagesInput)
def _get_messages(repo, db_context: dict[str, Any], data: m.GetMessagesInput) -> ToolResult:
    messages = repo.get_messages(data.session_id)
    db_context["messages"] = messages
    return ok({"messages": messages})


@tool("save_message", m.SaveMessageInput)
def _save_message(repo, _db_context: dict[str, Any], data: m.SaveMessageInput) -> ToolResult:
    msg_id = repo.save_message(
        session_id=data.session_id,
        role=data.role,
        content=data.content,
    )
    return ok({"message_id": msg_id})


@tool("quiz_pre_fetch", m.QuizPreFetchInput)
def _quiz_pre_fetch(repo, db_context: dict[str, Any], data: m.QuizPreFetchInput) -> ToolResult:
    topic_id = repo.upsert_topic(data.topic_name)
    wrong_questions = repo.get_wrong_questions(topic_id) if topic_id else []
    db_context["wrong_questions"] = wrong_questions
    db_context["quiz_topic_id"] = topic_id
    db_context["quiz_topic_name"] = data.topic_name
    return ok(
        {
            "topic_id": topic_id,
            "topic_name": data.topic_name,
            "wrong_questions": wrong_questions,
        }
    )


@tool("quiz_post_save", m.QuizPostSaveInput)
def _quiz_post_save(repo, _db_context: dict[str, Any], data: m.QuizPostSaveInput) -> ToolResult:
    saved_wrong = 0
    deleted_correct = 0
    failed_wrong = 0
    failed_correct = 0
    for entry in data.wrong_answers:
        try:
            repo.save_quiz_attempt(
                topic_id=data.topic_id,
                question=entry.get("question", ""),
                user_answer=entry.get("user_answer"),
                score=0.0,
                feedback=None,
            )
            saved_wrong += 1
        except Exception:
            failed_wrong += 1
    for attempt_id in data.correct_retries:
        try:
            repo.delete_quiz_attempt(attempt_id)
            deleted_correct += 1
        except Exception:
            failed_correct += 1
    if failed_wrong or failed_correct:
        return err(
            "db_error",
            "Failed to save some quiz results",
            {
                "saved_wrong": saved_wrong,
                "deleted_correct": deleted_correct,
                "failed_wrong": failed_wrong,
                "failed_correct": failed_correct,
            },
        )
    return ok({"saved_wrong": saved_wrong, "deleted_correct": deleted_correct})


def execute_tool(
    name: str,
    args: dict[str, Any],
    db_context: dict[str, Any],
    repo=None,
) -> ToolResult:
    repo = repo or get_repository()
    spec = get_tool(name)
    if spec is None:
        return err("unknown_tool", "Unknown tool", {"name": name})
    if args:
        allowed = set(spec.input_model.model_fields.keys())
        unexpected = [k for k in args.keys() if k not in allowed]
        if unexpected:
            fields = [{"field": key, "message": "Unexpected field"} for key in unexpected]
            return err("validation_error", "Invalid tool input", {"fields": fields})
        args = _strip_extras(spec.input_model, args)
    try:
        data = spec.input_model.model_validate(args or {})
    except ValidationError as exc:
        return _validation_error(exc)
    try:
        return spec.handler(repo, db_context, data)
    except Exception as exc:
        return _db_error(exc)


def _list_plan_items_impl(repo, db_context: dict[str, Any], plan_id: Any, plan_title: str | None) -> ToolResult:
    plans = db_context.get("plans") or repo.get_plans()
    db_context["plans"] = plans
    if plan_id == "latest":
        plan_id = repo.get_latest_plan_id()
    if plan_id is None and plan_title:
        candidates = _find_plan_candidates(plans, plan_title)
        if candidates:
            db_context["requested_plan_title"] = plan_title
        for candidate in candidates:
            items = repo.get_plan_items(candidate["plan_id"])
            db_context.setdefault("plan_items", {})[candidate["plan_id"]] = items
            db_context["requested_plan_id"] = candidate["plan_id"]
        if candidates:
            return ok({"plan_items": db_context.get("plan_items", {})})
        return _not_found("plan", {"plan_title": plan_title})
    if plan_id is not None:
        items = repo.get_plan_items(plan_id)
        db_context.setdefault("plan_items", {})[plan_id] = items
        db_context["requested_plan_id"] = plan_id
        return ok({"plan_items": db_context.get("plan_items", {})})
    return ok({"plan_items": {}})


def _find_plan_candidates(plans: list[dict[str, Any]], plan_title: str) -> list[dict[str, Any]]:
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
            exact.append(plan)
        elif lowered in title or title in lowered:
            contains.append(plan)
    candidates = exact + contains
    return [
        {"plan_id": candidate.get("plan_id"), "title": candidate.get("title"), "created_at": candidate.get("created_at")}
        for candidate in candidates
    ]

def _resolve_plan_from_args(
    repo,
    db_context: dict[str, Any],
    plan_id: int | str | None,
    plan_title: str | None,
) -> tuple[int | None, list[dict[str, Any]]]:
    if plan_id == "latest":
        latest_id = repo.get_latest_plan_id()
        if latest_id is None:
            return None, []
        return latest_id, [{"plan_id": latest_id, "title": None, "created_at": None}]
    plans = db_context.get("plans") or repo.get_plans()
    db_context["plans"] = plans
    if plan_id is not None:
        for plan in plans:
            if plan.get("plan_id") == plan_id:
                return plan_id, [
                    {"plan_id": plan_id, "title": plan.get("title"), "created_at": plan.get("created_at")}
                ]
        return None, []
    if plan_title:
        candidates = _find_plan_candidates(plans, plan_title)
        if len(candidates) == 1:
            return candidates[0]["plan_id"], candidates
        return None, candidates
    return None, []


def _find_item_candidates(repo, plan_id: int, item_title: str) -> list[dict[str, Any]]:
    items = repo.get_plan_items(plan_id)
    lowered = item_title.lower()
    exact = []
    contains = []
    for item in items:
        title = str(item.get("title", "")).lower()
        if title == lowered:
            exact.append(item)
        elif lowered in title or title in lowered:
            contains.append(item)
    candidates = exact + contains
    return [
        {"item_id": candidate.get("item_id"), "title": candidate.get("title"), "plan_id": plan_id}
        for candidate in candidates
    ]


def get_langchain_tools(db_context: dict[str, Any], repo=None):
    from langchain_core.tools import StructuredTool

    repo = repo or get_repository()

    class _ToolEnvelope(BaseModel):
        model_config = ConfigDict(extra="allow")
        kwargs: Any | None = None

    def _sanitize_tool_args(tool_name: str, raw_args: Any) -> dict[str, Any]:
        """Keep only declared fields for a tool; ignore LLM-invented extras."""
        if not isinstance(raw_args, dict):
            return {}
        spec = get_tool(tool_name)
        if spec is None:
            return {}
        allowed = set(spec.input_model.model_fields.keys())
        filtered = {k: v for k, v in raw_args.items() if k in allowed}
        return _strip_extras(spec.input_model, filtered)

    def _wrap(tool_name: str):
        def _tool(**kwargs):
            kwargs.pop("db_context", None)
            if "kwargs" in kwargs:
                if isinstance(kwargs["kwargs"], dict):
                    kwargs = kwargs["kwargs"]
                elif isinstance(kwargs["kwargs"], str):
                    try:
                        parsed = json.loads(kwargs["kwargs"])
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict):
                        kwargs = parsed
            kwargs = _sanitize_tool_args(tool_name, kwargs)
            return execute_tool(tool_name, kwargs, db_context, repo=repo)

        _tool.__doc__ = f"DB tool wrapper for {tool_name}."
        return _tool

    return [
        StructuredTool.from_function(
            _wrap(spec.name),
            name=spec.name,
            args_schema=_ToolEnvelope,
        )
        for spec in list_tools()
    ]
