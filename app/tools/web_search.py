"""Tavily web search tool node."""

from app.models.state import GraphState


def web_search_node(state: GraphState) -> dict:
    """Perform a web search via Tavily and return results.

    Populates: web_context.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``web_context``.
    """
    # TODO: Instantiate TavilySearchResults with settings.tavily_api_key
    # TODO: Invoke search with state["user_input"]
    # TODO: Format results into a readable string
    # TODO: Return {"web_context": formatted_results}
    pass
