"""Router agent node — classifies user intent and sets routing flags."""

from app.models.state import GraphState


def router_node(state: GraphState) -> dict:
    """Classify the user message and decide which tools/agents are needed.

    Populates: intent, needs_rag, needs_web, needs_db.

    Parameters
    ----------
    state : GraphState
        Current graph state with ``user_input`` populated.

    Returns
    -------
    dict
        Partial state update with routing fields.
    """
    # TODO: Build prompt from router template + state["user_input"]
    # TODO: Call LLM and parse JSON response
    # TODO: Return {"intent": ..., "needs_rag": ..., "needs_web": ..., "needs_db": ...}
    pass
