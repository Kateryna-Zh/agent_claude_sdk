from __future__ import annotations

from types import SimpleNamespace

from app.agents import db_agent
from app.agents import router_agent
from app.graph import routing
from app.schemas.router import RouterOutput


def test_router_plan_confirmation_sets_plan_confirmed(monkeypatch):
    def fake_invoke(_prompt):
        return SimpleNamespace(content="{}")

    def fake_parse(_raw, _schema, _retry):
        return RouterOutput(
            intent="PLAN",
            sub_intent="SAVE_PLAN",
            needs_rag=False,
            needs_web=False,
            needs_db=False,
            plan_title=None,
            item_title=None,
        )

    monkeypatch.setattr(router_agent, "get_chat_model", lambda: SimpleNamespace(invoke=fake_invoke))
    monkeypatch.setattr(router_agent, "parse_with_retry", fake_parse)

    state = {"user_input": "yes", "plan_draft": {"title": "Plan X", "items": []}}
    result = router_agent.router_node(state)

    assert result["plan_confirmed"] is True
    assert result["needs_db"] is True


def test_route_to_specialist_uses_plan_confirmed():
    state = {"intent": "PLAN", "plan_confirmed": True}
    assert routing.route_to_specialist(state) == "db"


def test_db_agent_fallback_review_uses_list_plan_items(monkeypatch):
    calls = []

    def fake_execute_tool(name, args, db_context, repo=None):
        calls.append((name, args))
        if name == "list_plan_items":
            db_context.setdefault("plan_items", {})[1] = []
        return {"ok": True, "data": {"plan_items": db_context.get("plan_items", {})}}

    monkeypatch.setattr(db_agent, "_run_tool_calling", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(db_agent, "execute_tool", fake_execute_tool)

    state = {
        "intent": "REVIEW",
        "user_input": "List items for Plan A",
        "db_context": {"requested_plan_title": "Plan A"},
    }
    db_agent.db_agent_node(state)

    assert calls == [("list_plan_items", {"plan_id": None, "plan_title": "Plan A"})]
