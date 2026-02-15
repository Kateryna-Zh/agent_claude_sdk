"""Tests for DB agent tool-error formatting."""

from app.agents import db_agent


def test_format_tool_error_validation_error_with_fields():
    tool_result = {
        "results": [
            {
                "result": {
                    "ok": False,
                    "error": {
                        "code": "validation_error",
                        "details": {"fields": [{"field": "user_id", "message": "Unexpected field"}]},
                    },
                }
            }
        ]
    }
    msg = db_agent._format_tool_error(tool_result)
    assert msg is not None
    assert "I need a bit more detail:" in msg
    assert "- user_id: Unexpected field" in msg


def test_format_tool_error_conflict_lists_candidates():
    tool_result = {
        "results": [
            {
                "result": {
                    "ok": False,
                    "error": {
                        "code": "conflict",
                        "details": {
                            "entity_type": "plan",
                            "candidates": [{"plan_id": 10, "title": "Python Plan", "created_at": "2026-01-01"}],
                        },
                    },
                }
            }
        ]
    }
    msg = db_agent._format_tool_error(tool_result)
    assert msg is not None
    assert "I found multiple plans" in msg
    assert "plan 10" in msg
    assert "'Python Plan'" in msg


def test_format_tool_error_not_found_plan_and_item():
    plan_result = {
        "results": [
            {
                "result": {
                    "ok": False,
                    "error": {
                        "code": "not_found",
                        "details": {"entity_type": "plan", "query": {"plan_title": "Missing Plan"}},
                    },
                }
            }
        ]
    }
    item_result = {
        "results": [
            {
                "result": {
                    "ok": False,
                    "error": {
                        "code": "not_found",
                        "details": {"entity_type": "item", "query": {"item_title": "Missing Item"}},
                    },
                }
            }
        ]
    }
    assert db_agent._format_tool_error(plan_result) == "I couldn't find a plan titled 'Missing Plan'."
    assert db_agent._format_tool_error(item_result) == "I couldn't find an item titled 'Missing Item'."


def test_format_tool_error_unknown_tool_and_db_error():
    unknown_tool_result = {
        "results": [{"result": {"ok": False, "error": {"code": "unknown_tool", "message": "Unknown tool"}}}]
    }
    db_error_result = {
        "results": [{"result": {"ok": False, "error": {"code": "db_error", "message": "Database error"}}}]
    }
    assert db_agent._format_tool_error(unknown_tool_result) == "That request is not supported yet."
    assert db_agent._format_tool_error(db_error_result) == "I hit a database error. Please try again."


def test_format_tool_error_permission_denied_and_fallback_message():
    denied_result = {
        "results": [{"result": {"ok": False, "error": {"code": "permission_denied", "message": "Not allowed"}}}]
    }
    fallback_result = {
        "results": [{"result": {"ok": False, "error": {"code": "other_code", "message": "Custom failure"}}}]
    }
    assert db_agent._format_tool_error(denied_result) == "Not allowed"
    assert db_agent._format_tool_error(fallback_result) == "Custom failure"

