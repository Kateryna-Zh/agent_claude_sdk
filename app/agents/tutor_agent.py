"""Tutor agent node — RAG-grounded explanations."""

from app.models.state import GraphState


def tutor_node(state: GraphState) -> dict:
    """Answer the user's question using retrieved RAG context.

    Populates: specialist_output.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``specialist_output``.
    """
    # TODO: Build prompt from tutor template + state["rag_context"] + state["user_input"]
    # TODO: Call LLM
    # TODO: Return {"specialist_output": llm_response}
    pass
