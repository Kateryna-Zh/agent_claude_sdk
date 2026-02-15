"""Tests for repository backend selection logic."""

import pytest

from app.db import repository_factory


def test_get_repository_returns_psycopg_when_backend_not_mcp(monkeypatch):
    monkeypatch.setattr(repository_factory.settings, "db_backend", "psycopg2")
    repo = repository_factory.get_repository()
    assert repo is repository_factory.get_psycopg_repository()


def test_get_repository_returns_mcp_repository_when_client_available(monkeypatch):
    monkeypatch.setattr(repository_factory.settings, "db_backend", "mcp")
    monkeypatch.setattr(repository_factory.mcp_manager, "get_client", lambda: object())
    repo = repository_factory.get_repository()
    assert isinstance(repo, repository_factory.MCPRepository)


def test_get_repository_falls_back_to_psycopg_when_mcp_unavailable_and_allowed(monkeypatch):
    monkeypatch.setattr(repository_factory.settings, "db_backend", "mcp")
    monkeypatch.setattr(repository_factory.settings, "mcp_fallback_to_psycopg2", True)
    monkeypatch.setattr(repository_factory.mcp_manager, "get_client", lambda: None)
    repo = repository_factory.get_repository()
    assert repo is repository_factory.get_psycopg_repository()


def test_get_repository_raises_when_mcp_unavailable_and_fallback_disabled(monkeypatch):
    monkeypatch.setattr(repository_factory.settings, "db_backend", "mcp")
    monkeypatch.setattr(repository_factory.settings, "mcp_fallback_to_psycopg2", False)
    monkeypatch.setattr(repository_factory.mcp_manager, "get_client", lambda: None)
    with pytest.raises(RuntimeError, match="MCP DB requested but client not available"):
        repository_factory.get_repository()

