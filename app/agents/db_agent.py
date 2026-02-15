"""DB agent node — executes DB tools via tool-calling or intent fallback."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.models.state import GraphState
from app.llm.ollama_client import get_chat_model
from app.tools.db_tools import execute_tool, get_langchain_tools

logger = logging.getLogger("uvicorn.error")

def db_agent_node(state: GraphState) -> dict:
    """Execute DB actions using tool-calling or intent fallback."""
    db_context = state.get("db_context") or {}

    intent = state.get("intent")

    # --- QUIZ intent: pre-fetch or post-save via tools ---
    if intent == "QUIZ":
        quiz_save = db_context.get("quiz_save")
        if quiz_save:
            return _handle_quiz_post_save(state, db_context, quiz_save)
        return _handle_quiz_pre_fetch(state, db_context)

    # Try tool-calling first (LangChain tools bound to the model).
    tool_result = _run_tool_calling(state, db_context)
    if tool_result is not None:
        logger.info("DB agent tool-calling returned %d result(s).", len(tool_result.get("results") or []))
        error_message = _format_tool_error(tool_result)
        if error_message:
            return {
                "user_response": error_message,
                "specialist_output": error_message,
                "db_context": db_context,
            }
        # Check if a status update happened — return confirmation instead of plan listing.
        confirmation = _format_tool_result_confirmation(tool_result)
        if confirmation:
            return {
                "user_response": confirmation,
                "specialist_output": confirmation,
                "db_context": db_context,
            }
        response = _format_db_response(db_context)
        return {
            "user_response": response,
            "specialist_output": response,
            "db_context": db_context,
        }

    # Fallback to intent-driven tools if tool-calling returns nothing.
    logger.info("DB agent fallback path (no tool-calls). intent=%s", intent)
    _execute_fallback_tools(state, db_context)
    response = _format_db_response(db_context)
    return {
        "user_response": response,
        "specialist_output": response,
        "db_context": db_context,
    }



def _patch_list_plan_items_args(args: dict[str, Any], db_context: dict[str, Any]) -> dict[str, Any]:
    """Fill in plan_id/title from db_context when LLM omitted them."""
    if args.get("plan_id") or args.get("plan_title"):
        return args
    if db_context.get("requested_plan_id") is not None:
        return {"plan_id": db_context.get("requested_plan_id")}
    if db_context.get("requested_plan_title"):
        return {"plan_title": db_context.get("requested_plan_title")}
    return args


def _patch_write_plan_args(args: dict[str, Any], state: GraphState) -> dict[str, Any] | None:
    """Ensure write_plan has full draft payload; return None to skip."""
    if not state.get("plan_confirmed"):
        logger.info("Skipping write_plan (plan not confirmed).")
        return None
    if not isinstance(args.get("items"), list):
        plan_draft = state.get("plan_draft") or {}
        args = {
            "title": plan_draft.get("title") or args.get("title"),
            "items": plan_draft.get("items") or [],
        }
        if not isinstance(args.get("items"), list):
            logger.info("Skipping write_plan (invalid items payload).")
            return None
    return args


def _run_tool_calling(state: GraphState, db_context: dict[str, Any]) -> dict[str, Any] | None:
    tools = get_langchain_tools(db_context)
    system = (
        "You are a DB agent. Use tools to read/write the database. "
        "Prefer tools over free-form text. "
        "If intent is PLAN and plan_confirmed is true, you MUST call write_plan with plan_draft. "
        "If intent is REVIEW, call list_plans or list_plan_items as needed. "
        "If intent is LOG_PROGRESS, call update_item_status or update_plan_status. "
        "If no tool is needed, respond without tool_calls."
    )
    user_payload = {
        "user_input": state.get("user_input"),
        "intent": state.get("intent"),
        "sub_intent": state.get("sub_intent"),
        "plan_confirmed": state.get("plan_confirmed"),
        "plan_draft": state.get("plan_draft"),
        "db_context": db_context,
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload)},
    ]

    llm = get_chat_model().bind_tools(tools)
    try:
        response = llm.invoke(messages)
    except Exception as exc:
        logger.warning("DB agent tool-calling failed: %s", exc)
        return None

    tool_calls = getattr(response, "tool_calls", None) or []
    if not tool_calls:
        return None

    tool_map = {tool.name: tool for tool in tools}
    results = []
    for call in tool_calls:
        name = call.get("name")
        args = call.get("args") or {}
        if name == "list_plan_items":
            args = _patch_list_plan_items_args(args, db_context)
        elif name == "write_plan":
            args = _patch_write_plan_args(args, state)
            if args is None:
                continue
        tool = tool_map.get(name)
        if tool is None:
            continue
        result = tool.invoke(args)
        logger.info("DB agent tool %s args=%s", name, json.dumps(args, ensure_ascii=False))
        results.append({"tool_call_id": call.get("id"), "name": name, "result": result})

    logger.info(
        "DB agent tool_calls: %s",
        json.dumps({"tool_calls": tool_calls, "results": results}, ensure_ascii=False),
    )

    return {"tool_calls": tool_calls, "results": results}


_CONFIRMATION_FORMATTERS = {
    "write_plan": lambda d: f"Plan created (plan {d.get('created_plan_id')}).",
    "add_plan_item": lambda d: f"Plan item added (item {d.get('item_id')}).",
    "update_item_status": lambda d: f"Status for item {d.get('item_id')} updated to {d.get('status')}.",
    "update_plan_status": lambda d: f"All items in plan {d.get('plan_id')} updated to {d.get('status')}.",
    "save_quiz_attempt": lambda d: f"Quiz attempt saved (attempt {d.get('attempt_id')}).",
    "quiz_post_save": lambda d: (
        f"Quiz results saved (wrong saved {d.get('saved_wrong')}, deleted correct {d.get('deleted_correct')})."
    ),
    "create_flashcard": lambda d: f"Flashcard created (card {d.get('card_id')}).",
    "update_flashcard_review": lambda d: f"Flashcard {d.get('card_id')} review updated.",
    "save_message": lambda d: "Message saved.",
}


def _format_tool_result_confirmation(tool_result: dict[str, Any]) -> str | None:
    """If tool results contain a status update or write, return a confirmation message."""
    results = tool_result.get("results") or []
    confirmations = []
    for r in results:
        name = r.get("name", "")
        result = r.get("result") or {}
        if not result.get("ok"):
            continue
        data = result.get("data") or {}
        formatter = _CONFIRMATION_FORMATTERS.get(name)
        if formatter:
            confirmations.append(formatter(data))
    return "\n".join(confirmations) if confirmations else None


def _format_tool_error(tool_result: dict[str, Any]) -> str | None:
    """Format tool errors into a user-facing clarification when possible."""
    results = tool_result.get("results") or []
    for r in results:
        result = r.get("result") or {}
        if result.get("ok") is not False:
            continue
        error = result.get("error") or {}
        code = error.get("code")
        if code == "conflict":
            return _format_conflict(error)
        if code == "validation_error":
            return _format_validation_error(error)
        if code == "not_found":
            return _format_not_found(error)
        if code == "permission_denied":
            return error.get("message") or "Permission denied for that request."
        if code == "unknown_tool":
            return "That request is not supported yet."
        if code == "db_error":
            return "I hit a database error. Please try again."
        return error.get("message") or "Something went wrong."
    return None


def _format_validation_error(error: dict[str, Any]) -> str:
    details = error.get("details") or {}
    fields = details.get("fields") or []
    if not fields:
        return "I couldn't validate that request. Please check your inputs."
    lines = ["I need a bit more detail:"]
    for f in fields:
        field = f.get("field", "field")
        msg = f.get("message", "Invalid value")
        lines.append(f"- {field}: {msg}")
    return "\n".join(lines)


def _format_not_found(error: dict[str, Any]) -> str:
    details = error.get("details") or {}
    entity_type = details.get("entity_type", "item")
    query = details.get("query") or {}
    if entity_type == "plan":
        plan_title = query.get("plan_title")
        plan_id = query.get("plan_id")
        if plan_title:
            return f"I couldn't find a plan titled '{plan_title}'."
        if plan_id:
            return f"I couldn't find plan {plan_id}."
        return "I couldn't find that plan."
    if entity_type == "item":
        item_title = query.get("item_title")
        if item_title:
            return f"I couldn't find an item titled '{item_title}'."
    return error.get("message") or "I couldn't find what you're looking for."


def _format_conflict(error: dict[str, Any]) -> str:
    details = error.get("details") or {}
    entity_type = details.get("entity_type", "item")
    candidates = details.get("candidates") or []
    if not candidates:
        return "I found multiple matches. Which one did you mean?"
    lines = [f"I found multiple {entity_type}s. Which one did you mean?"]
    for c in candidates:
        parts = []
        if c.get("plan_id") is not None:
            parts.append(f"plan {c.get('plan_id')}")
        if c.get("item_id") is not None:
            parts.append(f"item {c.get('item_id')}")
        title = c.get("title")
        if title:
            parts.append(f"'{title}'")
        created_at = c.get("created_at")
        if created_at:
            parts.append(f"created {created_at}")
        lines.append("- " + ", ".join(parts))
    return "\n".join(lines)


def _execute_fallback_tools(state: GraphState, db_context: dict[str, Any]) -> None:
    intent = state.get("intent")
    if intent == "REVIEW":
        plan_title = db_context.get("requested_plan_title")
        plan_id = db_context.get("requested_plan_id")
        if plan_title or plan_id:
            execute_tool(
                "list_plan_items",
                {"plan_id": plan_id, "plan_title": plan_title},
                db_context,
            )
            return
        _reset_plan_item_context(db_context)
        execute_tool("list_plans", {}, db_context)
        return
    if intent == "LOG_PROGRESS":
        item_title = db_context.get("requested_item_title")
        if item_title:
            result = execute_tool(
                "update_item_status",
                {"status": "in_progress", "item_title": item_title, "plan_id": "latest"},
                db_context,
            )
            if result.get("ok"):
                data = result.get("data") or {}
                db_context["_confirmation"] = f"Status for '{item_title}' updated to {data.get('status', 'in_progress')}."
            else:
                error = result.get("error") or {}
                if error.get("code") == "conflict":
                    db_context["_confirmation"] = _format_conflict(error)
                else:
                    db_context["_confirmation"] = f"Could not find item '{item_title}'."
        return


def _format_db_response(db_context: dict[str, Any]) -> str:
    # If a confirmation was set by a write operation, return it directly.
    confirmation = db_context.pop("_confirmation", None)
    if confirmation:
        return confirmation

    plans = db_context.get("plans") or []
    items_map = db_context.get("plan_items") or {}
    requested_plan_id = db_context.get("requested_plan_id")
    requested_plan_title = db_context.get("requested_plan_title")
    requested_items = bool(db_context.get("requested_items"))

    if not plans and not items_map:
        return "Done."

    items_only = requested_items or bool(requested_plan_id or requested_plan_title)
    if items_only:
        matching_ids = []
        if requested_plan_title:
            matching_ids = _resolve_plan_ids(plans, requested_plan_title)
        if requested_plan_id and requested_plan_id not in matching_ids:
            matching_ids.append(requested_plan_id)
        if not matching_ids:
            return "Which plan do you want the items for?"
        lines = ["Here are the items for your plan(s):"]
        found_any = False
        for plan_id in matching_ids:
            items = items_map.get(plan_id, [])
            if not items:
                continue
            found_any = True
            created_at = _lookup_plan_created_at(plans, plan_id)
            header = f"Plan ID {plan_id}"
            if created_at:
                header += f" (created {created_at})"
            lines.append(header + ":")
            for item in items:
                item_title = item.get("title", "Plan item")
                status = item.get("status", "pending")
                lines.append(f"- {item_title} [{status}]")
        if not found_any:
            return "No items found for the requested plan."
        return "\n".join(lines)

    lines = ["Here are your learning plans:"]
    seen_ids: set[int] = set()
    for plan in plans:
        plan_id = plan.get("plan_id")
        if plan_id in seen_ids:
            continue
        seen_ids.add(plan_id)
        lines.append(f"- {plan.get('title', 'Untitled plan')}")
    return "\n".join(lines)


def _resolve_plan_ids(plans: list[dict[str, Any]], plan_title: str) -> list[int]:
    """Find plan IDs matching a title string.

    Uses two-tier matching: exact matches (case-insensitive) are returned first,
    followed by substring matches where either the query contains the plan title
    or vice versa.
    """
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


def _lookup_plan_created_at(plans: list[dict[str, Any]], plan_id: int) -> str | None:
    for plan in plans:
        if plan.get("plan_id") == plan_id:
            return plan.get("created_at")
    return None


def _reset_plan_item_context(db_context: dict[str, Any]) -> None:
    db_context.pop("requested_plan_title", None)
    db_context.pop("requested_plan_id", None)
    db_context.pop("requested_items", None)
    db_context.pop("plan_items", None)


def _extract_topic_name(user_input: str) -> str:
    """Strip common quiz prefixes to get the topic name."""
    cleaned = re.sub(
        r'^(quiz|test|examine)\s+(me\s+)?(on|about)\s+',
        '', user_input, flags=re.IGNORECASE,
    ).strip()
    return cleaned or user_input


def _handle_quiz_pre_fetch(state: GraphState, db_context: dict[str, Any]) -> dict:
    """Pre-quiz: extract topic, upsert it, fetch previously-wrong questions."""
    user_input = (state.get("user_input") or "").strip()
    topic_name = _extract_topic_name(user_input)
    result = execute_tool("quiz_pre_fetch", {"topic_name": topic_name}, db_context)
    if not result.get("ok"):
        error = _format_tool_error({"results": [{"result": result}]})
        if error:
            return {"user_response": error, "specialist_output": error, "db_context": db_context}
    data = result.get("data") or {}
    db_context["quiz_topic_id"] = data.get("topic_id")
    db_context["quiz_topic_name"] = data.get("topic_name", topic_name)
    db_context["wrong_questions"] = data.get("wrong_questions") or []
    logger.info(
        "Quiz pre-fetch: topic=%s id=%s wrong_questions=%d",
        db_context.get("quiz_topic_name"),
        db_context.get("quiz_topic_id"),
        len(db_context.get("wrong_questions") or []),
    )
    return {"db_context": db_context}


def _handle_quiz_post_save(state: GraphState, db_context: dict[str, Any], quiz_save: dict[str, Any]) -> dict:
    """Post-quiz: persist wrong answers and remove correct retries."""
    db_context.pop("quiz_save", None)
    result = execute_tool(
        "quiz_post_save",
        {
            "topic_id": quiz_save.get("topic_id"),
            "wrong_answers": quiz_save.get("wrong_answers") or [],
            "correct_retries": quiz_save.get("correct_retries") or [],
        },
        db_context,
    )
    if not result.get("ok"):
        error = _format_tool_error({"results": [{"result": result}]})
        if error:
            return {"user_response": error, "specialist_output": error, "db_context": db_context}
    confirmation = _format_tool_result_confirmation({"results": [{"name": "quiz_post_save", "result": result}]})
    feedback = state.get("quiz_feedback")
    if feedback and confirmation:
        message = f"{feedback}\n\n{confirmation}"
        return {
            "user_response": message,
            "specialist_output": message,
            "db_context": db_context,
            "quiz_results_saved": True,
        }
    if feedback:
        return {
            "user_response": feedback,
            "specialist_output": feedback,
            "db_context": db_context,
            "quiz_results_saved": True,
        }
    if confirmation:
        return {
            "user_response": confirmation,
            "specialist_output": confirmation,
            "db_context": db_context,
            "quiz_results_saved": True,
        }
    return {"quiz_results_saved": True, "db_context": db_context}
