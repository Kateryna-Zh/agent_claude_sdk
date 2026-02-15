"""Tests for research agent formatting branches."""

from app.agents.research_agent import research_node


def test_research_node_returns_message_when_web_context_missing():
    result = research_node({"web_context": ""})
    assert result["user_response"] == "I couldn't find any web results to summarize for that question."
    assert result["specialist_output"] == result["user_response"]


def test_research_node_reports_no_update_mentions_when_keywords_absent():
    state = {
        "web_context": (
            "Result 1: General article\n"
            "URL: https://example.com/general\n"
            "Snippet: Introductory background on the topic.\n\n"
            "Result 2: Tutorial\n"
            "URL: https://example.com/tutorial\n"
            "Snippet: Step-by-step learning guide."
        )
    }
    result = research_node(state)
    output = result["specialist_output"]
    assert "No explicit update statements were found in the provided snippets." in output

