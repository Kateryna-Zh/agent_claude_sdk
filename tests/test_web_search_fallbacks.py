"""Tests for web-search fallback behavior."""

from app.tools import web_search as web_search_module


def test_web_search_node_falls_back_to_string_query_after_type_error(monkeypatch):
    monkeypatch.setattr(web_search_module.settings, "tavily_api_key", "test-key")

    class FakeTavilyTool:
        def __init__(self, **kwargs):
            self.calls = []

        def invoke(self, payload):
            self.calls.append(payload)
            if isinstance(payload, dict):
                raise TypeError("dict payload not supported")
            return [{"title": "Fallback result", "url": "https://example.com", "snippet": "latest update"}]

    monkeypatch.setattr(web_search_module, "TavilyTool", FakeTavilyTool)
    result = web_search_module.web_search_node({"user_input": "latest langchain news"})

    assert "Result 1: Fallback result" in result["web_context"]
    assert "https://example.com" in result["web_context"]


def test_web_search_node_stringifies_unknown_result_shapes(monkeypatch):
    monkeypatch.setattr(web_search_module.settings, "tavily_api_key", "test-key")

    class FakeTavilyTool:
        def __init__(self, **kwargs):
            pass

        def invoke(self, payload):
            return 12345

    monkeypatch.setattr(web_search_module, "TavilyTool", FakeTavilyTool)
    result = web_search_module.web_search_node({"user_input": "any query"})

    assert result["web_context"] == "12345"

