"""Conditional edge functions for the LangGraph graph."""

from app.models.state import GraphState


def route_after_router(state: GraphState) -> str:
    """Decide the next node after the router based on routing flags.

    Returns one of: 'retrieve_context', 'web_search', 'db_planner', 'specialist'.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    str
        The name of the next node.
    """
    if state.get("needs_db"):
        return "db_planner"
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
            return "review"
        return "planner"
    if intent == "QUIZ":
        return "quiz"
    if intent == "LATEST":
        return "research"
    if intent == "REVIEW":
        return "review"
    if intent == "LOG_PROGRESS":
        return "review"
    return "tutor"


def route_after_specialist(state: GraphState) -> str:
    """Decide whether to write to DB or go straight to formatting.

    Returns one of: 'db_write', 'format_response'.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    str
        The name of the next node.
    """
    if state.get("intent") == "PLAN":
        return "format_response"
    if state.get("intent") in {"QUIZ"}:
        return "db_write"
    if state.get("intent") in {"REVIEW", "LOG_PROGRESS"}:
        return "format_response"
    return "format_response"
