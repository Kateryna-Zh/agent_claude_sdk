"""Tests for quiz answer-key recovery retries."""

import app.agents.quiz_agent as quiz_agent


def test_quiz_generation_appends_answer_key_when_initial_output_has_none(monkeypatch):
    responses = [
        (
            "1. Question one?\n"
            "A) A\nB) B\nC) C\nD) D\n\n"
            "2. Question two?\n"
            "A) A\nB) B\nC) C\nD) D"
        ),
        "Answer key: 1:A, 2:B",
    ]

    monkeypatch.setattr(quiz_agent, "get_chat_model", lambda: object())
    monkeypatch.setattr(quiz_agent, "invoke_llm", lambda prompt, llm=None: responses.pop(0))

    result = quiz_agent.quiz_node(
        {
            "user_input": "Quiz me on Python",
            "db_context": {},
            "rag_context": "",
            "quiz_state": None,
        }
    )

    assert result["quiz_state"]["answer_key"] == {1: "A", 2: "B"}
    assert result["quiz_next_action"] == "format_response"


def test_quiz_generation_regenerates_when_answer_key_count_stays_mismatched(monkeypatch):
    responses = [
        (
            "1. First question?\n"
            "A) A\nB) B\nC) C\nD) D\n\n"
            "2. Second question?\n"
            "A) A\nB) B\nC) C\nD) D\n\n"
            "Answer key: 1:A"
        ),
        "Answer key: 1:A",
        (
            "1. First question?\n"
            "A) A\nB) B\nC) C\nD) D\n\n"
            "2. Second question?\n"
            "A) A\nB) B\nC) C\nD) D\n\n"
            "Answer key: 1:B, 2:C"
        ),
    ]
    prompts: list[str] = []

    monkeypatch.setattr(quiz_agent, "get_chat_model", lambda: object())

    def _fake_invoke(prompt, llm=None):
        prompts.append(prompt)
        return responses.pop(0)

    monkeypatch.setattr(quiz_agent, "invoke_llm", _fake_invoke)

    result = quiz_agent.quiz_node(
        {
            "user_input": "Quiz me on LangGraph",
            "db_context": {},
            "rag_context": "",
            "quiz_state": None,
        }
    )

    assert result["quiz_state"]["answer_key"] == {1: "B", 2: "C"}
    assert len(prompts) == 3
    assert "Regenerate the quiz as multiple-choice questions only." in prompts[-1]

