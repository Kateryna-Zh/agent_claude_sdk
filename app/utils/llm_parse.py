"""LLM JSON parsing helpers with schema validation and retry."""

from __future__ import annotations

import json
import re
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def parse_json_with_schema(raw: str, schema: Type[T]) -> T:
    data = json.loads(raw)
    if isinstance(data, dict):
        intent = data.get("intent")
        if isinstance(intent, str):
            data["intent"] = intent.strip().upper()
        for key in ("needs_rag", "needs_web", "needs_db"):
            if isinstance(data.get(key), str):
                data[key] = data[key].strip().lower() == "true"
    return schema.model_validate(data)


def _sanitize_invalid_escapes(raw: str) -> str:
    return re.sub(r'\\([^"\\/bfnrtu])', r"\1", raw)


def _extract_json_object(raw: str) -> str | None:
    if not raw:
        return None
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    for idx in range(start, len(raw)):
        char = raw[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw[start : idx + 1]
    return None


def parse_with_retry(raw: str, schema: Type[T], retry_fn) -> T:
    """Parse JSON with schema; retry once using retry_fn if invalid."""
    # TODO: Consider stricter validation + logging of raw vs sanitized JSON for transparency.
    if not raw or not raw.strip():
        corrected = retry_fn(raw)
        try:
            return parse_json_with_schema(corrected, schema)
        except json.JSONDecodeError:
            return parse_json_with_schema(_sanitize_invalid_escapes(corrected), schema)
    try:
        return parse_json_with_schema(raw, schema)
    except (json.JSONDecodeError, ValidationError):
        try:
            return parse_json_with_schema(_sanitize_invalid_escapes(raw), schema)
        except json.JSONDecodeError:
            extracted = _extract_json_object(raw)
            if extracted:
                try:
                    return parse_json_with_schema(_sanitize_invalid_escapes(extracted), schema)
                except (json.JSONDecodeError, ValidationError):
                    pass
            corrected = retry_fn(raw)
            if not corrected or not corrected.strip():
                extracted = _extract_json_object(raw)
                if extracted:
                    return parse_json_with_schema(_sanitize_invalid_escapes(extracted), schema)
            try:
                return parse_json_with_schema(corrected, schema)
            except json.JSONDecodeError:
                extracted = _extract_json_object(corrected)
                if extracted:
                    return parse_json_with_schema(_sanitize_invalid_escapes(extracted), schema)
                try:
                    return parse_json_with_schema(_sanitize_invalid_escapes(corrected), schema)
                except json.JSONDecodeError as exc:
                    raise ValueError("Unable to parse JSON after retries.") from exc
