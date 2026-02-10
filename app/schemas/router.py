"""Schemas for router and DB planner outputs."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class RouterOutput(BaseModel):
    intent: Literal["PLAN", "EXPLAIN", "QUIZ", "LOG_PROGRESS", "REVIEW", "LATEST"]
    sub_intent: str | None = None
    needs_rag: bool = False
    needs_web: bool = False
    needs_db: bool = False


class GetPlans(BaseModel):
    action: Literal["get_plans"]


class GetPlanItems(BaseModel):
    action: Literal["get_plan_items"]
    plan_id: int | Literal["latest"] | None = None
    plan_title: str | None = None


class CreatePlan(BaseModel):
    action: Literal["create_plan"]
    title: str


class AddPlanItem(BaseModel):
    action: Literal["add_plan_item"]
    plan_id: int | Literal["latest"]
    title: str
    topic: str | None = None
    due_date: str | None = None
    notes: str | None = None


class UpdatePlanItemStatus(BaseModel):
    action: Literal["update_plan_item_status"]
    item_id: int | None = None
    item_title: str | None = None
    plan_id: int | Literal["latest"] | None = None
    plan_title: str | None = None
    status: Literal["pending", "in_progress", "done"]


class UpdatePlanItemsStatus(BaseModel):
    action: Literal["update_plan_items_status"]
    plan_id: int | Literal["latest"]
    status: Literal["pending", "in_progress", "done"]


DBAction = (
    GetPlans
    | GetPlanItems
    | CreatePlan
    | AddPlanItem
    | UpdatePlanItemStatus
    | UpdatePlanItemsStatus
)


class DBPlanOutput(BaseModel):
    db_plan: list[DBAction] = Field(default_factory=list)
