"""Conditional edge functions for the LangGraph graph."""

import logging

from app.models.state import GraphState

logger = logging.getLogger("uvicorn.error")


def route_after_router(state: GraphState) -> str:
    """Decide the next node after the router based on routing flags.

    Returns one of: 'retrieve_context', 'web_search', 'db', or a specialist node.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    str
        The name of the next node.
    """
    if state.get("needs_db"):
        return "db"
    if state.get("needs_rag"):
        return "retrieve_context"
    if state.get("needs_web"):
        return "web_search"
    return route_to_specialist(state)


def route_to_specialist(state: GraphState) -> str:
    """Route to the correct specialist agent based on intent.

    Returns one of: 'planner', 'tutor', 'quiz', 'research'.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    str
        The name of the specialist node.
    """
    intent = state.get("intent")
    if intent == "PLAN":
        if state.get("plan_confirmed"):
            return "db"
        return "planner"
    if intent == "QUIZ":
        return "quiz"
    if intent == "LATEST":
        return "research"
    if intent == "REVIEW":
        return "db"
    if intent == "LOG_PROGRESS":
        return "db"
    return "tutor"

def route_after_db(state: GraphState) -> str:
     """After db node: for QUIZ pre-fetch, continue to RAG or quiz. Otherwise format."""
     intent = state.get("intent")
     if intent == "QUIZ" and not state.get("quiz_results_saved"):
         # Pre-quiz DB done → continue to RAG retrieval or quiz
         if state.get("needs_rag"):
             return "retrieve_context"
         return "quiz"
     # All other intents (REVIEW, LOG_PROGRESS, PLAN/SAVE_PLAN) + post-quiz DB
     return "format_response"


def route_after_quiz(state: GraphState) -> str:
    """After quiz node: if scoring produced save/delete instructions, route to db."""
    quiz_next = state.get("quiz_next_action")
    if quiz_next in {"db", "format_response"}:
        logger.info("route_after_quiz: quiz_next_action=%s", quiz_next)
        print(f"route_after_quiz -> {quiz_next}")
        return quiz_next
    db_context = state.get("db_context") or {}
    if db_context.get("quiz_save"):
        logger.info("route_after_quiz: inferred db (quiz_save present)")
        print("route_after_quiz -> db (quiz_save)")
        return "db"
    logger.info("route_after_quiz: default format_response")
    print("route_after_quiz -> format_response")
    return "format_response"
