"""Final response formatting tool node."""

from app.models.state import GraphState


def format_response_node(state: GraphState) -> dict:
    """Format the specialist output into the final user-facing response.

    Populates: final_response.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``final_response``.
    """
    # implement different formatting logic if needed, e.g. based on intent or specialist type
    response = state.get("user_response") or state.get("specialist_output") or ""
    # Preserve quiz_state for answer evaluation in subsequent turns.
    return {"final_response": response, "quiz_state": state.get("quiz_state")}
