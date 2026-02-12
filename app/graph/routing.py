"""Conditional edge functions for the LangGraph graph."""

from app.models.state import GraphState


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
        if state.get("sub_intent") == "SAVE_PLAN":
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
    db_context = state.get("db_context") or {}
    if db_context.get("quiz_save"):
        return "db"
    return "format_response"

