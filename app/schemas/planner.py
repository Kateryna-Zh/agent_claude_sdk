"""Schemas for planner output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlanItemDraft(BaseModel):
    title: str
    topic: str | None = None
    due_date: str | None = None
    notes: str | None = None


class PlanDraft(BaseModel):
    title: str
    items: list[PlanItemDraft] = Field(default_factory=list)


class PlannerOutput(BaseModel):
    user_response: str
    plan_draft: PlanDraft
