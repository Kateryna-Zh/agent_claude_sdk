"""Planner agent node — generates study plans."""

import json
import logging

from app.llm.ollama_client import get_chat_model
from app.prompts.planner import PLANNER_SYSTEM_PROMPT, PLANNER_USER_PROMPT
from app.schemas.planner import PlannerOutput
from app.utils.llm_parse import parse_with_retry

logger = logging.getLogger("uvicorn.error")
from app.models.state import GraphState


def planner_node(state: GraphState) -> dict:
    """Generate a study plan based on the user's learning goal.

    Populates: specialist_output.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``specialist_output``.
    """
    print("PLANNER HIT", flush=True)
    if state.get("plan_confirmed") and state.get("plan_draft"):
        return {
            "user_response": "Plan confirmed. Saving it now.",
            "specialist_output": "Plan confirmed. Saving it now.",
        }

    db_context = state.get("db_context") or {}
    prompt = PLANNER_SYSTEM_PROMPT + "\n\n" + PLANNER_USER_PROMPT.format(
        user_input=state.get("user_input", ""),
        plan_draft=json.dumps(state.get("plan_draft") or {}, ensure_ascii=False),
        db_context=json.dumps(db_context, ensure_ascii=False),
    )

    llm = get_chat_model()
    logger.info("Planner LLM call started")
    response = llm.invoke(prompt)
    logger.info("Planner LLM call finished")
    content = getattr(response, "content", str(response))

    def _retry(raw: str) -> str:
        fix_prompt = (
            "Fix the JSON to match the required schema. Output ONLY JSON."\
            f"\nRaw: {raw}"
        )
        retry_resp = llm.invoke(fix_prompt)
        return getattr(retry_resp, "content", str(retry_resp))

    parsed = parse_with_retry(content, PlannerOutput, _retry)

    user_response = parsed.user_response
    plan_draft = parsed.plan_draft.model_dump()

    if plan_draft and not _has_plan_content(user_response):
        user_response = _render_plan_markdown(plan_draft)

    return {
        "user_response": user_response,
        "specialist_output": user_response,
        "plan_draft": plan_draft,
    }


def _has_plan_content(text: str) -> bool:
    if not text:
        return False
    has_bullets = any(marker in text for marker in ("- ", "* ", "• "))
    return has_bullets


def _render_plan_markdown(plan_draft: dict) -> str:
    title = plan_draft.get("title") or "Study Plan"
    items = plan_draft.get("items") or []
    lines = [f"### {title}"]
    for item in items:
        item_title = item.get("title") if isinstance(item, dict) else None
        if item_title:
            lines.append(f"- {item_title}")
    lines.append("Want me to save this plan?")
    return "\n".join(lines)
