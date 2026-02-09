"""Planner agent node — generates study plans."""

from app.models.state import GraphState


def planner_node(state: GraphState) -> dict:
    """Generate a study plan based on the user's learning goal.

    Populates: specialist_output.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``specialist_output``.
    """
    # TODO: Build prompt from planner template + state["user_input"] + state["db_context"]
    # TODO: Call LLM
    # TODO: Return {"specialist_output": llm_response}
    pass
