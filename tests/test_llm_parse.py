"""Tests for JSON parsing and retry behavior."""

import pytest
from pydantic import ValidationError

from app.schemas.router import RouterOutput
from app.utils.llm_parse import parse_with_retry


def test_parse_with_retry_recovers_from_malformed_json():
    raw = 'Here is output: {"intent":"review","needs_rag":"false","needs_web":"false","needs_db":"true"'
    corrected = (
        '{"intent":"REVIEW","sub_intent":null,"needs_rag":false,"needs_web":false,'
        '"needs_db":true,"plan_title":null,"item_title":null}'
    )

    calls = {"count": 0}

    def _retry_fn(_bad_raw: str) -> str:
        calls["count"] += 1
        return corrected

    parsed = parse_with_retry(raw, RouterOutput, _retry_fn)
    assert parsed.intent == "REVIEW"
    assert parsed.needs_db is True
    assert calls["count"] == 1


def test_parse_with_retry_rejects_invalid_schema_types():
    raw = (
        '{"intent":"NOT_A_VALID_INTENT","sub_intent":null,"needs_rag":false,"needs_web":false,'
        '"needs_db":true,"plan_title":null,"item_title":null}'
    )

    with pytest.raises(ValidationError):
        parse_with_retry(raw, RouterOutput, lambda _raw: raw)
