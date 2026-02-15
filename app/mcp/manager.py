"""MCP server lifecycle manager."""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
from typing import Any

from langchain_mcp_adapters import client as mcp_client

from app.config import settings
from app.mcp.client import MCPClient

logger = logging.getLogger(__name__)


class MCPManager:
    """Start/stop an MCP stdio server and keep a client session alive."""

    def __init__(self) -> None:
        self._session_cm = None
        self._session = None
        self._client: MCPClient | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if settings.db_backend.lower() != "mcp":
            return
        async with self._lock:
            if self._session is not None:
                return
            connection = self._build_connection()
            self._session_cm = mcp_client.create_session(connection)
            self._session = await self._session_cm.__aenter__()
            await self._session.initialize()
            self._client = MCPClient(
                self._session,
                tool_name=settings.mcp_tool_name,
                query_key=settings.mcp_query_key,
                params_key=settings.mcp_params_key,
                supports_params=settings.mcp_supports_params,
            )
            logger.info("MCP server started")

    async def stop(self) -> None:
        async with self._lock:
            if self._session_cm is None:
                return
            await self._session_cm.__aexit__(None, None, None)
            self._session_cm = None
            self._session = None
            self._client = None
            logger.info("MCP server stopped")

    def get_client(self) -> MCPClient | None:
        return self._client

    def get_session(self):
        return self._session

    def _build_connection(self) -> dict[str, Any]:
        args = _parse_args(settings.mcp_server_args)
        env = os.environ.copy()
        if settings.mcp_database_url:
            env["DATABASE_URL"] = settings.mcp_database_url
        if settings.mcp_allow_write_ops:
            env["DANGEROUSLY_ALLOW_WRITE_OPS"] = "true"
        return {
            "transport": "stdio",
            "command": settings.mcp_server_command,
            "args": args,
            "env": env,
        }


mcp_manager = MCPManager()


def _parse_args(raw: str) -> list[str]:
    """Parse the MCP server arguments string into a list.

    Uses a comma-vs-space heuristic: if the string contains commas but no
    spaces it is treated as CSV (e.g. ``"--foo,--bar"``); otherwise it is
    parsed as a shell command line via ``shlex.split``.
    """
    if not raw:
        return []
    if "," in raw and " " not in raw:
        return [part for part in (seg.strip() for seg in raw.split(",")) if part]
    return shlex.split(raw)
