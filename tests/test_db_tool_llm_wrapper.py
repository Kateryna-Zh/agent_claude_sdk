"""Tests for LangChain DB tool wrapper input sanitization."""

from app.tools import db_tools


def _capture_execute_tool(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def _fake_execute_tool(name, args, db_context, repo=None):
        calls.append((name, args))
        return {"ok": True, "data": {}}

    monkeypatch.setattr(db_tools, "execute_tool", _fake_execute_tool)
    return calls


def _get_tool_by_name(tools, name: str):
    for tool in tools:
        if tool.name == name:
            return tool
    raise AssertionError(f"Tool not found: {name}")


def test_wrapper_drops_invented_args_for_list_plans(monkeypatch):
    calls = _capture_execute_tool(monkeypatch)
    tools = db_tools.get_langchain_tools(db_context={}, repo=object())
    list_plans = _get_tool_by_name(tools, "list_plans")

    list_plans.invoke({"kwargs": {"user_id": "your user id"}})

    assert calls[-1] == ("list_plans", {})


def test_wrapper_keeps_valid_args_and_drops_extra_fields(monkeypatch):
    calls = _capture_execute_tool(monkeypatch)
    tools = db_tools.get_langchain_tools(db_context={}, repo=object())
    list_items = _get_tool_by_name(tools, "list_plan_items")

    list_items.invoke({"kwargs": {"plan_title": "Python Plan", "user_id": "x"}})

    assert calls[-1] == ("list_plan_items", {"plan_title": "Python Plan"})


def test_wrapper_parses_kwargs_json_string_and_sanitizes(monkeypatch):
    calls = _capture_execute_tool(monkeypatch)
    tools = db_tools.get_langchain_tools(db_context={}, repo=object())
    list_items = _get_tool_by_name(tools, "list_plan_items")

    list_items.invoke({"kwargs": '{"plan_id":"latest","user_id":"x"}'})

    assert calls[-1] == ("list_plan_items", {"plan_id": "latest"})


def test_wrapper_handles_malformed_kwargs_json_without_crashing(monkeypatch):
    calls = _capture_execute_tool(monkeypatch)
    tools = db_tools.get_langchain_tools(db_context={}, repo=object())
    list_plans = _get_tool_by_name(tools, "list_plans")

    list_plans.invoke({"kwargs": "{not-json"})

    assert calls[-1] == ("list_plans", {})

