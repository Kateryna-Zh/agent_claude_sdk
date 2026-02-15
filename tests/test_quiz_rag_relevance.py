"""Tests for agentic KB relevance gating in quiz generation."""

from types import SimpleNamespace

import app.agents.quiz_agent as quiz_agent


class DummyLLM:
    def __init__(self, relevance: str, quiz_text: str):
        self.relevance = relevance
        self.quiz_text = quiz_text
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        if "relevance judge" in prompt or "Return ONLY one token" in prompt:
            return SimpleNamespace(content=self.relevance)
        return SimpleNamespace(content=self.quiz_text)


def _run_quiz_with_relevance(monkeypatch, relevance: str, rag_context: str):
    quiz_text = (
        "1. What is Rails?\n"
        "A) A gem\n"
        "B) A framework\n"
        "C) A database\n"
        "D) A server\n"
        "Answer key: 1:B"
    )
    dummy = DummyLLM(relevance=relevance, quiz_text=quiz_text)

    def _fake_get_chat_model():
        return dummy

    monkeypatch.setattr(quiz_agent, "get_chat_model", _fake_get_chat_model)
    monkeypatch.setattr(
        quiz_agent,
        "invoke_llm",
        lambda prompt, llm=None: dummy.invoke(prompt).content,
    )

    state = {
        "user_input": "Ruby on Rails",
        "db_context": {},
        "rag_context": rag_context,
        "quiz_state": None,
    }
    result = quiz_agent.quiz_node(state)
    return result, dummy


def test_quiz_drops_rag_context_when_irrelevant(monkeypatch):
    rag_context = "Unrelated KB content about Kubernetes."
    _, dummy = _run_quiz_with_relevance(monkeypatch, "NO", rag_context)
    generation_prompt = dummy.prompts[-1]
    assert "Knowledge base context:" in generation_prompt
    assert rag_context not in generation_prompt


def test_quiz_keeps_rag_context_when_relevant(monkeypatch):
    rag_context = "Ruby on Rails is a web framework."
    _, dummy = _run_quiz_with_relevance(monkeypatch, "YES", rag_context)
    generation_prompt = dummy.prompts[-1]
    assert rag_context in generation_prompt
