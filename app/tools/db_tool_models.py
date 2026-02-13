from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PlanId = int | Literal["latest"]
Status = Literal["pending", "in_progress", "done"]


class BaseToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListPlansInput(BaseToolModel):
    pass


class ListPlanItemsInput(BaseToolModel):
    # Intentionally optional: listing without a selector should return empty results.
    plan_id: PlanId | None = None
    plan_title: str | None = None


class WritePlanItem(BaseToolModel):
    title: str = Field(min_length=1)
    due_date: str | None = None
    notes: str | None = None


class WritePlanInput(BaseToolModel):
    title: str = Field(min_length=1)
    items: list[WritePlanItem] = Field(default_factory=list)


class AddPlanItemInput(BaseToolModel):
    plan_id: PlanId
    title: str = Field(min_length=1)
    due_date: str | None = None
    notes: str | None = None


class UpdateItemStatusInput(BaseToolModel):
    status: Status
    item_id: int | None = None
    item_title: str | None = None
    plan_id: PlanId | None = None
    plan_title: str | None = None

    @model_validator(mode="after")
    def _require_item_selector(self) -> "UpdateItemStatusInput":
        # Note: without a plan selector, item_title may still fail to resolve and return not_found.
        if self.item_id is None and not (self.item_title or "").strip():
            raise ValueError("item_id or item_title is required")
        return self


class UpdatePlanStatusInput(BaseToolModel):
    status: Status
    plan_id: PlanId | None = None
    plan_title: str | None = None

    @model_validator(mode="after")
    def _require_plan_selector(self) -> "UpdatePlanStatusInput":
        if self.plan_id is None and not (self.plan_title or "").strip():
            raise ValueError("plan_id or plan_title is required")
        return self


class SaveQuizAttemptInput(BaseToolModel):
    topic_id: int | None = None
    question: str = Field(min_length=1)
    user_answer: str | None = None
    score: float | None = None
    feedback: str | None = None


class GetWrongQuestionsInput(BaseToolModel):
    topic_id: int = Field(ge=1)


class DeleteQuizAttemptInput(BaseToolModel):
    attempt_id: int = Field(ge=1)


class GetWeakTopicsInput(BaseToolModel):
    limit: int = Field(default=5, ge=1, le=100)


class GetDueFlashcardsInput(BaseToolModel):
    limit: int = Field(default=10, ge=1, le=100)


class CreateFlashcardInput(BaseToolModel):
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    topic_id: int | None = None


class UpdateFlashcardReviewInput(BaseToolModel):
    card_id: int = Field(ge=1)
    ease_factor: float | None = Field(default=None, ge=1.0, le=5.0)
    next_review_at: str | None = None


class GetMessagesInput(BaseToolModel):
    session_id: int = Field(ge=1)


class SaveMessageInput(BaseToolModel):
    session_id: int = Field(ge=1)
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)


class QuizPreFetchInput(BaseToolModel):
    topic_name: str = Field(min_length=1)


class QuizPostSaveInput(BaseToolModel):
    topic_id: int = Field(ge=1)
    wrong_answers: list[dict[str, Any]] = Field(default_factory=list)
    correct_retries: list[int] = Field(default_factory=list)

    @field_validator("correct_retries")
    @classmethod
    def _retry_ids_positive(cls, value: list[int]) -> list[int]:
        if any(v <= 0 for v in value):
            raise ValueError("correct_retries must contain positive integers")
        return value
