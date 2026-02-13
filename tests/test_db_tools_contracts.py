from __future__ import annotations

from typing import Any

import pytest

from app.tools.db_tools import execute_tool


class FakeRepo:
    def __init__(self):
        self.plans = [
            {"plan_id": 1, "title": "Plan A", "created_at": "2025-01-01"},
            {"plan_id": 2, "title": "Plan B", "created_at": "2025-01-02"},
        ]
        self.plan_items = {
            1: [
                {"item_id": 10, "title": "Item 1", "status": "pending"},
                {"item_id": 11, "title": "Item 2", "status": "done"},
            ],
            2: [],
        }
        self.created_plan_id = 100
        self.created_items: list[dict[str, Any]] = []

    def get_plans(self):
        return list(self.plans)

    def get_plan_items(self, plan_id: int):
        return list(self.plan_items.get(plan_id, []))

    def get_latest_plan_id(self):
        return max(p["plan_id"] for p in self.plans)

    def create_plan(self, title: str) -> int:
        self.plans.append({"plan_id": self.created_plan_id, "title": title, "created_at": "2025-02-01"})
        return self.created_plan_id

    def add_plan_item(self, plan_id: int, title: str, topic_id=None, due_date=None, notes=None) -> int:
        item_id = 200 + len(self.created_items)
        self.created_items.append(
            {
                "plan_id": plan_id,
                "title": title,
                "topic_id": topic_id,
                "due_date": due_date,
                "notes": notes,
            }
        )
        self.plan_items.setdefault(plan_id, []).append(
            {"item_id": item_id, "title": title, "status": "pending"}
        )
        return item_id

    def update_plan_item_status(self, item_id: int, status: str) -> None:
        for items in self.plan_items.values():
            for item in items:
                if item["item_id"] == item_id:
                    item["status"] = status
                    return


def test_list_plans_success():
    repo = FakeRepo()
    db_context = {}
    result = execute_tool("list_plans", {}, db_context, repo=repo)
    assert result["ok"] is True
    assert "plans" in result["data"]
    assert len(result["data"]["plans"]) == 2


def test_list_plan_items_success_by_id():
    repo = FakeRepo()
    db_context = {}
    result = execute_tool("list_plan_items", {"plan_id": 1}, db_context, repo=repo)
    assert result["ok"] is True
    items_map = result["data"]["plan_items"]
    assert 1 in items_map
    assert len(items_map[1]) == 2


def test_write_plan_success():
    repo = FakeRepo()
    db_context = {}
    payload = {"title": "New Plan", "items": [{"title": "First item"}]}
    result = execute_tool("write_plan", payload, db_context, repo=repo)
    assert result["ok"] is True
    assert result["data"]["created_plan_id"] == repo.created_plan_id
    assert len(repo.created_items) == 1


def test_update_item_status_success_by_id():
    repo = FakeRepo()
    db_context = {}
    result = execute_tool("update_item_status", {"item_id": 10, "status": "done"}, db_context, repo=repo)
    assert result["ok"] is True
    assert result["data"]["item_id"] == 10
    assert result["data"]["status"] == "done"


@pytest.mark.parametrize(
    "tool_name,args",
    [
        ("list_plan_items", {"unexpected": "field"}),
        ("write_plan", {"title": ""}),
        ("update_item_status", {"status": "done"}),
    ],
)
def test_validation_error(tool_name: str, args: dict[str, Any]):
    repo = FakeRepo()
    db_context = {}
    result = execute_tool(tool_name, args, db_context, repo=repo)
    assert result["ok"] is False
    assert result["error"]["code"] == "validation_error"
