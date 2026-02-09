"""PostgreSQL read tool node."""

from app.models.state import GraphState


def db_read_node(state: GraphState) -> dict:
    """Read relevant data from PostgreSQL based on intent.

    Populates: db_context.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``db_context``.
    """
    # TODO: Based on state["intent"], call the appropriate repository functions:
    #   - QUIZ / REVIEW → get_weak_topics(), get_due_flashcards()
    #   - PLAN / LOG_PROGRESS → get_plan_items()
    #   - Otherwise → get_messages(session_id)
    # TODO: Return {"db_context": fetched_data}
    pass
