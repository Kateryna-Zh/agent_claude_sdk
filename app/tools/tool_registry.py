from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from pydantic import BaseModel

from app.tools.contracts import ToolResult


@dataclass(frozen=True)
class ToolSpec:
    name: str
    input_model: type[BaseModel]
    handler: Callable[[Any, dict[str, Any], BaseModel], ToolResult]


_TOOL_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> None:
    _TOOL_REGISTRY[spec.name] = spec


def get_tool(name: str) -> ToolSpec | None:
    return _TOOL_REGISTRY.get(name)


def list_tools() -> Iterable[ToolSpec]:
    return list(_TOOL_REGISTRY.values())
