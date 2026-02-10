"""Interactive CLI client for /chat endpoint."""

from __future__ import annotations

import argparse
import json
import sys

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive chat CLI")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/chat",
        help="Chat endpoint URL",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds",
    )
    args = parser.parse_args()

    session_id = None
    print("Type your messages. Ctrl+D or 'exit' to quit.")

    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break

        payload = {"message": user_input}
        if session_id is not None:
            payload["session_id"] = session_id

        resp = requests.post(args.url, json=payload, timeout=args.timeout)
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {resp.text}")
            continue

        data = resp.json()
        session_id = data.get("session_id", session_id)
        reply = data.get("reply", "")
        print(reply)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
