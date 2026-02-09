"""Quiz agent node — generates and evaluates quizzes."""

from app.models.state import GraphState


def quiz_node(state: GraphState) -> dict:
    """Generate quiz questions or evaluate a quiz answer.

    Populates: specialist_output.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``specialist_output``.
    """
    # TODO: Determine mode (generate vs evaluate) from state["user_input"]
    # TODO: Build prompt from quiz template + state["db_context"]
    # TODO: Call LLM
    # TODO: Return {"specialist_output": llm_response}
    pass
