"""Stable idempotency keys and bounded correlation identifiers."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{1,31}$")


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Payload must be JSON serializable.") from exc


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def make_idempotency_key(namespace: str, payload: Any) -> str:
    if not NAMESPACE_PATTERN.fullmatch(namespace):
        raise ValueError(
            "Namespace must be 2-32 lowercase letters, digits, dots, dashes, or underscores."
        )
    return f"{namespace}:{payload_hash(payload)}"


def validate_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ValueError("Idempotency key must be 8-128 safe identifier characters.")
    return normalized


def normalize_correlation_id(value: str | None) -> str:
    if value:
        normalized = value.strip()
        if IDENTIFIER_PATTERN.fullmatch(normalized):
            return normalized
    return str(uuid.uuid4())
