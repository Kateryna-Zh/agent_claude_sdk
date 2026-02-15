"""Canonical row extraction for MCP server payloads."""

from __future__ import annotations

from typing import Any

from app.utils.constants import MCP_ROW_KEYS


def extract_rows(payload: Any) -> list[dict[str, Any]]:
    """Extract row dicts from an MCP query response.

    Handles three payload shapes:
    - ``list`` — returned directly (filtering non-dict entries).
    - ``dict`` — probes *MCP_ROW_KEYS* for a nested list/dict, with
      recursive descent into nested dicts.
    - ``None`` / other — returns ``[]``.
    """
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in MCP_ROW_KEYS:
            if key in payload:
                value = payload[key]
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
                if isinstance(value, dict):
                    nested = extract_rows(value)
                    if nested:
                        return nested
        if "row" in payload and isinstance(payload["row"], dict):
            return [payload["row"]]
    return []
