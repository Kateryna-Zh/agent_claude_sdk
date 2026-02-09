"""CLI to verify MCP DB connectivity without agent logic."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any

from app.config import settings
from app.db.mcp_repository import _inline_params
from app.mcp.client import extract_payload
from app.mcp.manager import mcp_manager


def _describe_result(result: Any) -> dict[str, Any]:
    info: dict[str, Any] = {"type": type(result).__name__}
    for attr in ("structuredContent", "content", "isError"):
        if hasattr(result, attr):
            info[attr] = getattr(result, attr)
    if hasattr(result, "model_dump"):
        try:
            info["model_dump"] = result.model_dump()
        except Exception:
            info["model_dump"] = "error"
    return info

logger = logging.getLogger(__name__)


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "result", "results"):
            if key in payload:
                value = payload[key]
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
                if isinstance(value, dict):
                    nested = _extract_rows(value)
                    if nested:
                        return nested
        if "row" in payload and isinstance(payload["row"], dict):
            return [payload["row"]]
    return []


async def run_check(message: str, debug: bool, cleanup: bool) -> int:
    await mcp_manager.start()
    try:
        session = mcp_manager.get_session()
        if session is None:
            raise RuntimeError("MCP session not available")

        tool = settings.mcp_tool_name
        if debug:
            tools_result = await session.list_tools()
            raw_tools = getattr(tools_result, "tools", tools_result)
            tools = list(raw_tools) if raw_tools is not None else []
            print("available tools:", [t.name for t in tools])
            for t in tools:
                if t.name == tool:
                    print("tool schema:", t.inputSchema)
                    break

        def _args(sql: str, params: list[Any] | None = None) -> dict[str, Any]:
            params = params or []
            if params and not settings.mcp_supports_params:
                sql = _inline_params(sql, params)
                params = []
            args = {settings.mcp_query_key: sql}
            if settings.mcp_supports_params and params:
                args[settings.mcp_params_key] = params
            return args

        create_session = await session.call_tool(tool, _args(
            "INSERT INTO sessions DEFAULT VALUES RETURNING session_id"
        ))
        if debug:
            print("create_session raw result:", _describe_result(create_session))
        create_payload = extract_payload(create_session)
        if debug:
            print("create_session raw payload:", create_payload)
        session_rows = _extract_rows(create_payload)
        if not session_rows:
            raise RuntimeError("No session_id returned from MCP")
        session_id = session_rows[0]["session_id"]

        insert_message = await session.call_tool(
            tool,
            _args(
                "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s) RETURNING id",
                [session_id, "assistant", message],
            ),
        )
        if debug:
            print("insert_message raw result:", _describe_result(insert_message))
        insert_payload = extract_payload(insert_message)
        if debug:
            print("insert_message raw payload:", insert_payload)
        message_rows = _extract_rows(insert_payload)
        if not message_rows:
            raise RuntimeError("No message id returned from MCP")
        message_id = message_rows[0]["id"]

        fetch_messages = await session.call_tool(
            tool,
            _args(
                "SELECT id, role, content, created_at FROM messages WHERE session_id = %s ORDER BY created_at",
                [session_id],
            ),
        )
        if debug:
            print("fetch_messages raw result:", _describe_result(fetch_messages))
        fetch_payload = extract_payload(fetch_messages)
        if debug:
            print("fetch_messages raw payload:", fetch_payload)
        messages = _extract_rows(fetch_payload)
        found = any(row.get("id") == message_id for row in messages)

        if cleanup:
            await session.call_tool(
                tool,
                _args(
                    "DELETE FROM messages WHERE id = %s",
                    [message_id],
                ),
            )
            await session.call_tool(
                tool,
                _args(
                    "DELETE FROM sessions WHERE session_id = %s",
                    [session_id],
                ),
            )

        print("MCP check results")
        print(f"session_id: {session_id}")
        print(f"message_id: {message_id}")
        print(f"messages_found: {len(messages)}")
        print(f"message_present: {found}")
        print(f"cleanup: {cleanup}")

        return 0 if found else 2
    finally:
        await mcp_manager.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify MCP DB connectivity")
    parser.add_argument(
        "--message",
        default="mcp connectivity check",
        help="Message to write for the test",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print raw MCP payloads for troubleshooting",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the test rows after verification",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        return asyncio.run(run_check(args.message, args.debug, args.cleanup))
    except Exception:
        logger.exception("MCP check failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
