"""Tests for quiz scoring and save payload behavior."""

import app.agents.quiz_agent as quiz_agent


def test_quiz_node_returns_error_when_answer_key_missing():
    state = {
        "user_input": "1:A, 2:B",
        "quiz_state": {"quiz_text": "1. Q1\n2. Q2", "answer_key": {}},
        "db_context": {},
    }

    result = quiz_agent.quiz_node(state)

    assert "I couldn't find an answer key" in result["user_response"]
    assert result["quiz_next_action"] == "format_response"


def test_quiz_node_scoring_builds_quiz_save_and_routes_to_db():
    state = {
        "user_input": "1:A, 2:C, 3:D",
        "quiz_state": {
            "answer_key": {1: "A", 2: "B"},
            "quiz_text": (
                "1. What is Python?\n"
                "A) Language\n"
                "B) Database\n\n"
                "2. What is LangGraph?\n"
                "A) OS\n"
                "B) Framework"
            ),
            "topic_id": 42,
            "retry_attempt_ids": {1: 9001},
        },
        "db_context": {},
    }

    result = quiz_agent.quiz_node(state)
    output = result["user_response"]
    quiz_save = result["db_context"]["quiz_save"]

    assert "Score: 0.50" in output
    assert "Wrong:" in output
    assert "No answer key:" in output
    assert "Warning: Missing answer key entries for: 3." in output
    assert result["quiz_next_action"] == "db"
    assert result["quiz_state"] is None
    assert quiz_save["topic_id"] == 42
    assert quiz_save["correct_retries"] == [9001]
    assert len(quiz_save["wrong_answers"]) == 1
    assert quiz_save["wrong_answers"][0]["question"] == "What is LangGraph?"
    assert quiz_save["wrong_answers"][0]["user_answer"] == "C"

