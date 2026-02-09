"""PostgreSQL write tool node."""

from app.models.state import GraphState


def db_write_node(state: GraphState) -> dict:
    """Persist specialist output to PostgreSQL based on intent.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Empty dict (no state fields to update).
    """
    # TODO: Based on state["intent"]:
    #   - PLAN → create_plan() + add_plan_item() for each item
    #   - QUIZ → save_quiz_attempt()
    #   - LOG_PROGRESS → update_plan_item_status()
    # TODO: Always save_message(session_id, "assistant", specialist_output)
    # TODO: Return {}
    pass
