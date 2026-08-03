"""Recursive, field-name based evidence redaction."""

from __future__ import annotations

from typing import Any

REDACTED = "[REDACTED]"
DEFAULT_REDACTED_FIELDS = frozenset(
    {"authorization", "api_key", "apikey", "password", "secret", "token"}
)


def redact(value: Any, fields: frozenset[str] = DEFAULT_REDACTED_FIELDS) -> Any:
    lowered = {field.lower() for field in fields}
    if isinstance(value, dict):
        return {
            str(key): REDACTED if str(key).lower() in lowered else redact(item, fields)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, fields) for item in value]
    if isinstance(value, tuple):
        return [redact(item, fields) for item in value]
    return value
