"""Research agent node — summarises web search results."""

from app.models.state import GraphState


def research_node(state: GraphState) -> dict:
    """Summarise web search results into a user-friendly briefing.

    Populates: specialist_output.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``specialist_output``.
    """
    # TODO: Build prompt from research template + state["web_context"] + state["user_input"]
    # TODO: Call LLM
    # TODO: Return {"specialist_output": llm_response}
    pass
