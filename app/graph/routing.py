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

