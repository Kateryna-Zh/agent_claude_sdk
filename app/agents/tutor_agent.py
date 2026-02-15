"""Tutor agent node — RAG-grounded explanations."""

import logging

from app.prompts.tutor import (
    TUTOR_SYSTEM_PROMPT,
    TUTOR_USER_PROMPT,
    GENERAL_TUTOR_SYSTEM_PROMPT,
)
from app.models.state import GraphState
from app.utils.llm_helpers import invoke_llm

logger = logging.getLogger("uvicorn.error")


def tutor_node(state: GraphState) -> dict:
    """Answer the user's question using retrieved RAG context.

    Populates: specialist_output.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``specialist_output``.
    """
    logger.info("TUTOR HIT")
    rag_context = state.get("rag_context", "")
    user_input = state.get("user_input", "")
    if rag_context.strip():
        prompt = TUTOR_SYSTEM_PROMPT + "\n\n" + TUTOR_USER_PROMPT.format(
            user_input=user_input,
            rag_context=rag_context,
        )
    else:
        prompt = GENERAL_TUTOR_SYSTEM_PROMPT + "\n\n" + TUTOR_USER_PROMPT.format(
            user_input=user_input,
            rag_context="",
        )
    content = invoke_llm(prompt)
    return {"user_response": content, "specialist_output": content}
