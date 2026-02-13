from __future__ import annotations

from typing import Any, Literal
from typing_extensions import NotRequired, TypedDict


ErrorCode = Literal[
    "validation_error",
    "not_found",
    "conflict",
    "unknown_tool",
    "db_error",
    "permission_denied",
]


class ToolError(TypedDict):
    code: ErrorCode
    message: str
    details: NotRequired[dict[str, Any]]


class ToolSuccess(TypedDict):
    ok: Literal[True]
    data: dict[str, Any]


class ToolFailure(TypedDict):
    ok: Literal[False]
    error: ToolError


ToolResult = ToolSuccess | ToolFailure


def ok(data: dict[str, Any]) -> ToolSuccess:
    return {"ok": True, "data": data}


def err(code: ErrorCode, message: str, details: dict[str, Any] | None = None) -> ToolFailure:
    return {"ok": False, "error": {"code": code, "message": message, "details": details}}
