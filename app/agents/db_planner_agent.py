"""DB planner agent — produces a DB action plan.

TODO(deletion): This agent is not wired into the current graph. If it remains unused,
remove this file and its prompt to reduce maintenance surface.
"""

from __future__ import annotations

import json

from app.llm.ollama_client import get_chat_model
from app.models.state import GraphState
from app.prompts.db_planner import DB_PLANNER_SYSTEM_PROMPT, DB_PLANNER_USER_PROMPT
from app.schemas.router import DBPlanOutput
from app.utils.llm_parse import parse_with_retry


def db_planner_node(state: GraphState) -> dict:
    """Create a DB action plan for review/progress/save operations."""
    # TODO: Re-ask LLM for item_title when no DB item matches.
    intent = state.get("intent")
    sub_intent = state.get("sub_intent")
    if intent == "REVIEW" and sub_intent in {"LIST_PLANS", "LIST_ITEMS"}:
        if sub_intent == "LIST_PLANS":
            db_plan = [{"action": "get_plans"}]
        else:
            llm = get_chat_model()
            plan_title = (state.get("db_context") or {}).get("requested_plan_title")
            if not plan_title:
                plan_title = _extract_plan_title(llm, state.get("user_input", ""))
            db_plan = [
                {"action": "get_plans"},
                {"action": "get_plan_items", "plan_id": None, "plan_title": plan_title},
            ]
        logger = __import__("logging").getLogger("uvicorn.error")
        logger.info("DB planner shortcut plan: %s", db_plan)
        return {"db_plan": db_plan}

    if intent == "LOG_PROGRESS" and (sub_intent == "UPDATE_STATUS" or sub_intent is None):
        llm = get_chat_model()
        plan_title = (state.get("db_context") or {}).get("requested_plan_title")
        item_title = _extract_item_title(llm, state.get("user_input", ""))
        status = _extract_status(llm, state.get("user_input", ""))
        db_plan = [
            {
                "action": "update_plan_item_status",
                "item_id": None,
                "item_title": item_title,
                "plan_id": "latest" if not plan_title else None,
                "plan_title": plan_title,
                "status": status,
            }
        ]
        logger = __import__("logging").getLogger("uvicorn.error")
        logger.info("DB planner shortcut plan: %s", db_plan)
        return {"db_plan": db_plan}

    prompt = DB_PLANNER_SYSTEM_PROMPT + "\n\n" + DB_PLANNER_USER_PROMPT.format(
        user_input=state.get("user_input", ""),
        intent=state.get("intent", ""),
        sub_intent=state.get("sub_intent", ""),
        plan_draft=json.dumps(state.get("plan_draft") or {}, ensure_ascii=False),
    )
    llm = get_chat_model()
    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response))

    def _retry(raw: str) -> str:
        fix_prompt = (
            "Fix the JSON to match the required schema. Output ONLY JSON."\
            f"\nRaw: {raw}"
        )
        retry_resp = llm.invoke(fix_prompt)
        return getattr(retry_resp, "content", str(retry_resp))

    parsed = parse_with_retry(content, DBPlanOutput, _retry)
    logger = __import__("logging").getLogger("uvicorn.error")
    logger.info("DB planner output (raw): %s", parsed.model_dump())

    db_plan = parsed.db_plan
    sub_intent = state.get("sub_intent")
    intent = state.get("intent")
    if intent == "REVIEW" and sub_intent in {"LIST_PLANS", "LIST_ITEMS"} and db_plan:
        filtered = [step for step in db_plan if step.get("action") != "create_plan"]
        if filtered != db_plan:
            logger.info("DB planner filtered create_plan for review request: %s", filtered)
        db_plan = filtered

    if intent == "REVIEW" and sub_intent == "LIST_ITEMS":
        has_items = any(step.get("action") == "get_plan_items" for step in db_plan)
        if not has_items:
            plan_title = state.get("user_input", "").strip() or None
            db_plan.append({"action": "get_plan_items", "plan_id": None, "plan_title": plan_title})
            logger.info("DB planner appended get_plan_items: %s", db_plan)
    if not db_plan:
        logger.info("DB planner override check intent=%s sub_intent=%s user_input=%s", intent, sub_intent, state.get("user_input"))
        if sub_intent == "LIST_PLANS" or (intent == "REVIEW" and sub_intent is None):
            db_plan = [{"action": "get_plans"}]
        elif sub_intent == "LIST_ITEMS" or (intent == "REVIEW" and sub_intent == "LIST_ITEMS"):
            plan_title = state.get("user_input", "").strip() or None
            db_plan = [
                {"action": "get_plans"},
                {"action": "get_plan_items", "plan_id": None, "plan_title": plan_title},
            ]

    logger.info("DB planner final plan: %s", db_plan)
    return {"db_plan": db_plan}


def _extract_plan_title(llm, user_input: str) -> str | None:
    prompt = (
        "Extract the plan title from the user message. "
        "Return ONLY the plan title as plain text, or empty if none.\n"
        f"User message: {user_input}"
    )
    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response)).strip()
    return content or None


def _extract_item_title(llm, user_input: str) -> str | None:
    prompt = (
        "Extract the learning item title from the user message. "
        "Return ONLY the item title as plain text, or empty if none.\n"
        f"User message: {user_input}"
    )
    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response)).strip().strip('"').strip("'")
    return content or None


def _extract_status(llm, user_input: str) -> str:
    prompt = (
        "Classify the status implied by the user message.\n"
        "Map phrases like started/began/in progress -> in_progress; "
        "finished/completed/done -> done; otherwise pending.\n"
        "Return ONLY one of: pending, in_progress, done.\n"
        f"User message: {user_input}"
    )
    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response)).strip().lower()
    if content in {"pending", "in_progress", "done"}:
        return content
    return "in_progress"
