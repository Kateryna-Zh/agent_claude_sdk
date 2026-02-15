"""Router agent node — classifies user intent and sets routing flags."""

import logging

from app.llm.ollama_client import get_chat_model
from app.models.state import GraphState
from app.prompts.router import ROUTER_SYSTEM_PROMPT, ROUTER_USER_PROMPT
from app.schemas.router import RouterOutput
from app.utils.constants import HAS_QUIZ_ANSWERS_RE
from app.utils.llm_helpers import invoke_llm
from app.utils.llm_parse import parse_with_retry

logger = logging.getLogger("uvicorn.error")


def router_node(state: GraphState) -> dict:
    """Classify the user message and decide which tools/agents are needed.

    Populates: intent, needs_rag, needs_web, needs_db.
    """
    user_input = state.get("user_input", "")
    # Fast-path: if we have a pending quiz and the user answered with numbered choices,
    # skip LLM routing and go straight to QUIZ evaluation.
    quiz_state = state.get("quiz_state") or {}
    if quiz_state and HAS_QUIZ_ANSWERS_RE.search(user_input):
        return {
            "intent": "QUIZ",
            "sub_intent": None,
            "needs_rag": False,
            "needs_web": False,
            "needs_db": False,
            "plan_confirmed": False,
            "db_context": state.get("db_context") or {},
        }
    plan_draft_present = bool(state.get("plan_draft"))
    prompt = ROUTER_SYSTEM_PROMPT + "\n\n" + ROUTER_USER_PROMPT.format(
        user_input=user_input,
        last_intent=state.get("last_intent"),
        plan_draft_present=plan_draft_present,
    )
    llm = get_chat_model()
    logger.info("Router LLM call started")
    content = invoke_llm(prompt, llm)
    logger.info("Router LLM call finished")

    def _retry(raw: str) -> str:
        fix_prompt = (
            "Fix the JSON to match this exact schema and keys. Output ONLY JSON.\n"
            "Required keys: intent, sub_intent, needs_rag, needs_web, needs_db, plan_title, item_title.\n"
            "Use ONLY these keys; do not use needs_localKnowledge or other variants.\n"
            'Valid intents: "PLAN","EXPLAIN","QUIZ","LOG_PROGRESS","REVIEW","LATEST".\n'
            "Schema example:\n"
            '{"intent":"REVIEW","sub_intent":"LIST_ITEMS","needs_rag":false,"needs_web":false,"needs_db":true,"plan_title":"Learning Plan for HTML","item_title":null}\n'
            f"Raw: {raw}"
        )
        return invoke_llm(fix_prompt, llm)

    try:
        parsed = parse_with_retry(content, RouterOutput, _retry)
    except ValueError as exc:
        logger.error("Router parse failed, falling back to defaults: %s", exc)
        parsed = RouterOutput(
            intent="EXPLAIN",
            sub_intent=None,
            needs_rag=False,
            needs_web=False,
            needs_db=False,
            plan_title=None,
            item_title=None,
        )
    logger.info("Router parsed output: %s", parsed.model_dump())

    plan_confirmed = False
    needs_db = parsed.needs_db
    if parsed.intent == "PLAN" and parsed.sub_intent == "SAVE_PLAN" and state.get("plan_draft"):
        plan_confirmed = True
        needs_db = True
    elif parsed.intent == "PLAN":
        # Do not hit DB for new plan drafts until user confirms saving.
        needs_db = False
    elif parsed.intent in {"REVIEW", "LOG_PROGRESS"}:
        needs_db = True
    elif parsed.intent == "QUIZ":
        needs_db = True  # Always check for prior wrong questions

    # Populate db_context with extracted titles so downstream nodes can use them.
    db_context = state.get("db_context") or {}
    if parsed.plan_title:
        db_context["requested_plan_title"] = parsed.plan_title
    if parsed.item_title:
        db_context["requested_item_title"] = parsed.item_title

    needs_web = parsed.intent == "LATEST"
    if parsed.intent == "LATEST":
        parsed.needs_rag = False

    final = {
        "intent": parsed.intent,
        "sub_intent": parsed.sub_intent,
        "needs_rag": parsed.needs_rag,
        "needs_web": needs_web,
        "needs_db": needs_db,
        "plan_confirmed": plan_confirmed,
        "db_context": db_context,
    }
    logger.info("Router final output: %s", final)
    return final
