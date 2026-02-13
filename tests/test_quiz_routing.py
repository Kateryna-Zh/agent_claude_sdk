"""Tests for quiz routing decisions."""

from app.graph.routing import route_after_quiz


def test_route_after_quiz_respects_quiz_next_action():
    state = {
        "quiz_next_action": "format_response",
        "db_context": {"quiz_save": {"topic_id": 1}},
    }
    assert route_after_quiz(state) == "format_response"


def test_route_after_quiz_falls_back_to_db_on_quiz_save():
    state = {
        "db_context": {"quiz_save": {"topic_id": 1}},
    }
    assert route_after_quiz(state) == "db"


def test_route_after_quiz_defaults_to_format_response():
    state = {
        "db_context": {},
    }
    assert route_after_quiz(state) == "format_response"
