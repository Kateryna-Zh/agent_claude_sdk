"""Schemas for router output."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel


class RouterOutput(BaseModel):
    intent: Literal["PLAN", "EXPLAIN", "QUIZ", "LOG_PROGRESS", "REVIEW", "LATEST"]
    sub_intent: str | None = None
    needs_rag: bool = False
    needs_web: bool = False
    needs_db: bool = False
    plan_title: str | None = None
    item_title: str | None = None
