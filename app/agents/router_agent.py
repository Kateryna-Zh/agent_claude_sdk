"""Router agent node — classifies user intent and sets routing flags."""

import logging

from app.llm.ollama_client import get_chat_model
from app.models.state import GraphState
from app.prompts.router import ROUTER_SYSTEM_PROMPT, ROUTER_USER_PROMPT
from app.schemas.router import RouterOutput
from app.utils.llm_parse import parse_with_retry

logger = logging.getLogger("uvicorn.error")


def router_node(state: GraphState) -> dict:
    """Classify the user message and decide which tools/agents are needed.

    Populates: intent, needs_rag, needs_web, needs_db.
    """
    user_input = state.get("user_input", "")
    plan_draft_present = bool(state.get("plan_draft"))
    prompt = ROUTER_SYSTEM_PROMPT + "\n\n" + ROUTER_USER_PROMPT.format(
        user_input=user_input,
        last_intent=state.get("last_intent"),
        plan_draft_present=plan_draft_present,
    )
    llm = get_chat_model()
    logger.info("Router LLM call started")
    response = llm.invoke(prompt)
    logger.info("Router LLM call finished")
    content = getattr(response, "content", str(response))

    def _retry(raw: str) -> str:
        fix_prompt = (
            "Fix the JSON to match this exact schema and keys. Output ONLY JSON.\n"
            "Required keys: intent, sub_intent, needs_rag, needs_web, needs_db.\n"
            "Use ONLY these keys; do not use needs_localKnowledge or other variants.\n"
            'Valid intents: "PLAN","EXPLAIN","QUIZ","LOG_PROGRESS","REVIEW","LATEST".\n'
            "Schema example:\n"
            '{"intent":"REVIEW","sub_intent":"LIST_PLANS","needs_rag":false,"needs_web":false,"needs_db":true}\n'
            f"Raw: {raw}"
        )
        retry_resp = llm.invoke(fix_prompt)
        return getattr(retry_resp, "content", str(retry_resp))

    parsed = parse_with_retry(content, RouterOutput, _retry)
    logger.info("Router parsed output: %s", parsed.model_dump())

    plan_confirmed = False
    needs_db = parsed.needs_db
    if parsed.sub_intent in {"LIST_ITEMS", "LIST_PLANS"}:
        parsed.intent = "REVIEW"
        needs_db = True
    if state.get("last_intent") == "REVIEW" and parsed.intent in {"EXPLAIN", "PLAN"}:
        parsed.intent = "REVIEW"
        parsed.sub_intent = parsed.sub_intent or "LIST_ITEMS"
        needs_db = True
    if parsed.intent == "PLAN" and parsed.sub_intent == "SAVE_PLAN" and state.get("plan_draft"):
        plan_confirmed = True
        needs_db = True
    elif parsed.intent == "PLAN":
        clarified = _clarify_plan_intent(llm, user_input)
        if clarified == "LIST_ITEMS":
            parsed.intent = "REVIEW"
            parsed.sub_intent = "LIST_ITEMS"
            needs_db = True
        elif clarified == "LIST_PLANS":
            parsed.intent = "REVIEW"
            parsed.sub_intent = "LIST_PLANS"
            needs_db = True
        elif clarified == "CREATE":
            needs_db = False
    elif parsed.intent in {"REVIEW", "LOG_PROGRESS"}:
        needs_db = True

    final = {
        "intent": parsed.intent,
        "sub_intent": parsed.sub_intent,
        "needs_rag": parsed.needs_rag,
        "needs_web": parsed.needs_web,
        "needs_db": needs_db,
        "plan_confirmed": plan_confirmed,
    }
    logger.info("Router final output: %s", final)
    return final


def _clarify_plan_intent(llm, user_input: str) -> str:
    prompt = (
        "You classify if the user wants to CREATE a new plan or VIEW existing plans.\n"
        "Return ONLY one token: CREATE, LIST_PLANS, LIST_ITEMS, or OTHER.\n"
        f"User message: {user_input}"
    )
    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response))
    return content.strip().upper()
