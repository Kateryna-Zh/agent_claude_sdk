"""Tests for web search routing and summarization flow."""

from app.agents.research_agent import research_node
from app.graph.routing import route_after_router
from app.tools import web_search as web_search_module


def test_route_after_router_selects_web_search():
    state = {"needs_db": False, "needs_rag": False, "needs_web": True, "intent": "LATEST"}
    assert route_after_router(state) == "web_search"


def test_web_search_node_returns_empty_when_query_missing():
    assert web_search_module.web_search_node({"user_input": ""}) == {"web_context": ""}


def test_web_search_node_returns_unavailable_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(web_search_module.settings, "tavily_api_key", "")
    state = {"user_input": "latest python releases"}
    result = web_search_module.web_search_node(state)
    assert "TAVILY_API_KEY not configured" in result["web_context"]


def test_web_search_node_formats_top_two_results(monkeypatch):
    monkeypatch.setattr(web_search_module.settings, "tavily_api_key", "test-key")

    class FakeTavilyTool:
        def __init__(self, **kwargs):
            assert kwargs["max_results"] == 2
            assert kwargs["tavily_api_key"] == "test-key"

        def invoke(self, payload):
            assert payload == {"query": "latest langgraph updates"}
            return {
                "results": [
                    {"title": "Release 1", "url": "https://example.com/r1", "content": "Release notes v1"},
                    {"title": "Release 2", "link": "https://example.com/r2", "snippet": "Version 2 announced"},
                    {"title": "Release 3", "url": "https://example.com/r3", "content": "Should be truncated"},
                ]
            }

    monkeypatch.setattr(web_search_module, "TavilyTool", FakeTavilyTool)
    result = web_search_module.web_search_node({"user_input": "latest langgraph updates"})
    text = result["web_context"]
    assert "Result 1: Release 1" in text
    assert "URL: https://example.com/r1" in text
    assert "Snippet: Release notes v1" in text
    assert "Result 2: Release 2" in text
    assert "https://example.com/r2" in text
    assert "Release 3" not in text


def test_research_node_summarizes_update_mentions():
    state = {
        "web_context": (
            "Result 1: LangGraph changelog\n"
            "URL: https://example.com/changelog\n"
            "Snippet: Latest release notes describe version 1.2 changes.\n\n"
            "Result 2: Blog post\n"
            "URL: https://example.com/blog\n"
            "Snippet: Introductory overview."
        )
    }
    result = research_node(state)
    output = result["specialist_output"]
    assert output.startswith("Based on the provided web results")
    assert "LangGraph changelog" in output
    assert "Possible update-related mentions found in snippets:" in output

