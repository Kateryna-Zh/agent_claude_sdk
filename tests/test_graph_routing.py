"""Tests for graph routing after DB node."""

from app.graph.routing import route_after_db


def test_route_after_db_quiz_with_rag_goes_to_retrieve_context():
    state = {"intent": "QUIZ", "quiz_results_saved": False, "needs_rag": True}
    assert route_after_db(state) == "retrieve_context"


def test_route_after_db_quiz_without_rag_goes_to_quiz():
    state = {"intent": "QUIZ", "quiz_results_saved": False, "needs_rag": False}
    assert route_after_db(state) == "quiz"


def test_route_after_db_non_quiz_goes_to_format_response():
    state = {"intent": "REVIEW", "quiz_results_saved": False}
    assert route_after_db(state) == "format_response"

