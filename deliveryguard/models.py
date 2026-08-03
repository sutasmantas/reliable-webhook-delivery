"""Typed delivery states and transport-independent outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Classification(str, Enum):
    SUCCESS = "success"
    ALREADY_APPLIED = "already_applied"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    CLIENT_ERROR = "client_error"
    MALFORMED_RESPONSE = "malformed_response"
    CONFIGURATION_ERROR = "configuration_error"
    WORKER_INTERRUPTED = "worker_interrupted"


class ActionState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    DELIVERED = "delivered"
    ALREADY_APPLIED = "already_applied"
    DEAD_LETTER = "dead_letter"


TERMINAL_STATES = {
    ActionState.DELIVERED,
    ActionState.ALREADY_APPLIED,
    ActionState.DEAD_LETTER,
}


@dataclass(frozen=True)
class DeliveryResult:
    classification: Classification
    http_status: int | None = None
    response: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.classification not in {
            Classification.SUCCESS,
            Classification.ALREADY_APPLIED,
        }:
            raise ValueError("A delivery result must be a successful outcome.")


class DeliveryFailure(RuntimeError):
    """A normalized failure safe to persist and use in retry decisions."""

    def __init__(
        self,
        classification: Classification,
        message: str,
        *,
        retryable: bool,
        http_status: int | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        if classification in {Classification.SUCCESS, Classification.ALREADY_APPLIED}:
            raise ValueError("Successful classifications cannot be failures.")
        self.classification = classification
        self.retryable = retryable
        self.http_status = http_status
        self.evidence = evidence or {}
        super().__init__(message)


@dataclass(frozen=True)
class ActionRecord:
    id: str
    idempotency_key: str
    destination: str
    state: ActionState
    correlation_id: str
    payload_hash: str
    request: dict[str, Any]
    attempt_count: int
    max_attempts: int
    cycle: int
    last_classification: Classification | None
    last_error: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AttemptReceipt:
    sequence: int
    action_id: str
    cycle: int
    cycle_attempt: int
    classification: Classification
    retryable: bool
    http_status: int | None
    latency_ms: float
    request: dict[str, Any]
    response: dict[str, Any]
    error: str | None
    correlation_id: str
    created_at: str
