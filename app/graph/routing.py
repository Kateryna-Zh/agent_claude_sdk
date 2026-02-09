"""Conditional edge functions for the LangGraph graph."""

from app.models.state import GraphState


def route_after_router(state: GraphState) -> str:
    """Decide the next node after the router based on routing flags.

    Returns one of: 'retrieve_context', 'web_search', 'db_read', 'specialist'.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    str
        The name of the next node.
    """
    # TODO: Check needs_rag, needs_web, needs_db flags
    # TODO: Prioritise: rag > web > db > specialist
    pass


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
    # TODO: Map intent to specialist node name
    # TODO: PLAN → 'planner', EXPLAIN → 'tutor', QUIZ → 'quiz', LATEST → 'research'
    pass


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
    # TODO: Write to DB for PLAN, QUIZ, LOG_PROGRESS intents
    # TODO: Otherwise skip to format_response
    pass
