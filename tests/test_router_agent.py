"""Tests for router agent normalization and fallbacks."""

from types import SimpleNamespace

from app.agents import router_agent
from app.schemas.router import RouterOutput


def _stub_llm(monkeypatch):
    monkeypatch.setattr(router_agent, "get_chat_model", lambda: SimpleNamespace())
    monkeypatch.setattr(router_agent, "invoke_llm", lambda *_args, **_kwargs: "{}")


def test_router_falls_back_to_defaults_when_parse_fails(monkeypatch):
    _stub_llm(monkeypatch)
    monkeypatch.setattr(router_agent, "parse_with_retry", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad")))

    result = router_agent.router_node({"user_input": "??"})

    assert result["intent"] == "EXPLAIN"
    assert result["needs_rag"] is False
    assert result["needs_web"] is False
    assert result["needs_db"] is False
    assert result["plan_confirmed"] is False


def test_router_latest_forces_web_and_disables_rag(monkeypatch):
    _stub_llm(monkeypatch)
    monkeypatch.setattr(
        router_agent,
        "parse_with_retry",
        lambda *_args, **_kwargs: RouterOutput(
            intent="LATEST",
            sub_intent=None,
            needs_rag=True,
            needs_web=False,
            needs_db=False,
            plan_title=None,
            item_title=None,
        ),
    )

    result = router_agent.router_node({"user_input": "latest langchain updates"})

    assert result["intent"] == "LATEST"
    assert result["needs_web"] is True
    assert result["needs_rag"] is False
    assert result["needs_db"] is False


def test_router_quiz_forces_db_true(monkeypatch):
    _stub_llm(monkeypatch)
    monkeypatch.setattr(
        router_agent,
        "parse_with_retry",
        lambda *_args, **_kwargs: RouterOutput(
            intent="QUIZ",
            sub_intent=None,
            needs_rag=False,
            needs_web=False,
            needs_db=False,
            plan_title=None,
            item_title=None,
        ),
    )

    result = router_agent.router_node({"user_input": "quiz me on python"})
    assert result["needs_db"] is True


def test_router_review_and_log_progress_force_db_true(monkeypatch):
    _stub_llm(monkeypatch)

    def _parsed(intent: str) -> RouterOutput:
        return RouterOutput(
            intent=intent,  # type: ignore[arg-type]
            sub_intent=None,
            needs_rag=False,
            needs_web=False,
            needs_db=False,
            plan_title=None,
            item_title=None,
        )

    monkeypatch.setattr(router_agent, "parse_with_retry", lambda *_args, **_kwargs: _parsed("REVIEW"))
    review_result = router_agent.router_node({"user_input": "list my plans"})
    assert review_result["needs_db"] is True

    monkeypatch.setattr(router_agent, "parse_with_retry", lambda *_args, **_kwargs: _parsed("LOG_PROGRESS"))
    progress_result = router_agent.router_node({"user_input": "I finished topic X"})
    assert progress_result["needs_db"] is True


def test_router_copies_plan_and_item_titles_to_db_context(monkeypatch):
    _stub_llm(monkeypatch)
    monkeypatch.setattr(
        router_agent,
        "parse_with_retry",
        lambda *_args, **_kwargs: RouterOutput(
            intent="LOG_PROGRESS",
            sub_intent=None,
            needs_rag=False,
            needs_web=False,
            needs_db=True,
            plan_title="React Plan",
            item_title="Hooks",
        ),
    )

    result = router_agent.router_node({"user_input": "I started Hooks", "db_context": {}})

    assert result["db_context"]["requested_plan_title"] == "React Plan"
    assert result["db_context"]["requested_item_title"] == "Hooks"

