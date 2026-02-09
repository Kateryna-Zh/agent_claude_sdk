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
    # TODO: Take state["specialist_output"] and format it nicely
    # TODO: Optionally add session metadata, citations, etc.
    # TODO: Return {"final_response": formatted_text}
    pass
