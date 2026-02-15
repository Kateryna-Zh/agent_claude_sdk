"""Tests for FastAPI /chat endpoint contract."""

from fastapi.testclient import TestClient

import app.main as main


class _DummyRepo:
    def create_session(self) -> int:
        return 101


class _DummyGraph:
    def __init__(self, result):
        self._result = result

    def invoke(self, _state):
        return dict(self._result)


async def _noop_async():
    return None


def test_chat_endpoint_returns_reply_and_session_id(monkeypatch):
    monkeypatch.setattr(main.settings, "db_backend", "psycopg2")
    monkeypatch.setattr(main, "get_repository", lambda: _DummyRepo())
    monkeypatch.setattr(main.mcp_manager, "start", _noop_async)
    monkeypatch.setattr(main.mcp_manager, "stop", _noop_async)
    monkeypatch.setattr(
        main,
        "graph",
        _DummyGraph({"final_response": "Hi there", "intent": "EXPLAIN", "db_context": {}, "quiz_state": None}),
    )

    with TestClient(main.app) as client:
        response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == 101
    assert payload["reply"] == "Hi there"


def test_chat_endpoint_returns_504_on_timeout(monkeypatch):
    monkeypatch.setattr(main.settings, "db_backend", "psycopg2")
    monkeypatch.setattr(main, "get_repository", lambda: _DummyRepo())
    monkeypatch.setattr(main.mcp_manager, "start", _noop_async)
    monkeypatch.setattr(main.mcp_manager, "stop", _noop_async)
    monkeypatch.setattr(
        main,
        "graph",
        _DummyGraph({"final_response": "should not return", "intent": "EXPLAIN", "db_context": {}, "quiz_state": None}),
    )
    monkeypatch.setattr(main.concurrent.futures, "wait", lambda *_args, **_kwargs: (set(), set()))

    with TestClient(main.app) as client:
        response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 504
    assert response.json()["detail"] == "Chat processing timed out"

