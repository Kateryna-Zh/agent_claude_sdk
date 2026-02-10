"""Tavily web search tool node."""

import logging

from app.config import settings
from app.models.state import GraphState

try:
    from langchain_tavily import TavilySearch
    TavilyTool = TavilySearch
except ImportError:  # pragma: no cover - fallback for older installs
    try:
        from langchain_tavily import TavilySearchResults
        TavilyTool = TavilySearchResults
    except ImportError:
        from langchain_community.tools.tavily_search import TavilySearchResults
        TavilyTool = TavilySearchResults

logger = logging.getLogger("uvicorn.error")


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
    query = (state.get("user_input") or "").strip()
    if not query:
        return {"web_context": ""}
    if not settings.tavily_api_key:
        return {"web_context": "Web search is unavailable: TAVILY_API_KEY not configured."}

    logger.info("WEB SEARCH HIT")
    search = TavilyTool(max_results=2, tavily_api_key=settings.tavily_api_key)

    try:
        results = search.invoke({"query": query})
    except TypeError:
        # Some tool versions accept a raw string input.
        results = search.invoke(query)

    if isinstance(results, dict) and "results" in results:
        results_list = results.get("results") or []
    elif isinstance(results, list):
        results_list = results
    else:
        return {"web_context": str(results).strip()}

    lines = []
    for idx, item in enumerate(results_list[:2], start=1):
        if not isinstance(item, dict):
            lines.append(f"Result {idx}: {item}")
            continue
        title = item.get("title") or item.get("name") or "Untitled"
        url = item.get("url") or item.get("link") or ""
        snippet = item.get("content") or item.get("snippet") or item.get("summary") or ""
        entry = f"Result {idx}: {title}"
        if url:
            entry += f"\nURL: {url}"
        if snippet:
            entry += f"\nSnippet: {snippet}"
        lines.append(entry.strip())

    formatted_results = "\n\n".join(lines).strip() or "No results found."
    logger.info("WEB SEARCH RESULTS: %s", len(results_list[:2]))
    return {"web_context": formatted_results}
