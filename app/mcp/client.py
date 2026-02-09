"""MCP client wrapper for PostgreSQL queries."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_payload(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured

    content = getattr(result, "content", None)
    if not content:
        return None

    text_parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            text_parts.append(item)
        elif isinstance(item, dict) and item.get("type") == "text":
            text_parts.append(item.get("text", ""))
        elif hasattr(item, "text"):
            text_parts.append(getattr(item, "text"))

    if not text_parts:
        return None

    text = "\n".join(text_parts).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.debug("MCP returned non-JSON text payload")
        return {"text": text}


class MCPClient:
    """Thin sync wrapper around an async MCP ClientSession."""

    def __init__(
        self,
        session,
        *,
        tool_name: str,
        query_key: str = "query",
        params_key: str = "params",
        supports_params: bool = False,
    ) -> None:
        self._session = session
        self._tool_name = tool_name
        self._query_key = query_key
        self._params_key = params_key
        self._supports_params = supports_params

    def query(self, sql: str, params: list[Any] | None = None) -> Any:
        """Execute a query via MCP and return structured content if available."""
        payload = self._run_async(self._call(sql, params or []))
        return extract_payload(payload)

    async def async_query(self, sql: str, params: list[Any] | None = None) -> Any:
        result = await self._call(sql, params or [])
        return extract_payload(result)

    async def _call(self, sql: str, params: list[Any]) -> Any:
        tool_args = {self._query_key: sql}
        if self._supports_params and self._params_key and params:
            tool_args[self._params_key] = params
        return await self._session.call_tool(self._tool_name, tool_args)

    def _run_async(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        raise RuntimeError(
            "MCPClient.query() cannot be used inside a running event loop. "
            "Use MCPClient.async_query() instead."
        )
