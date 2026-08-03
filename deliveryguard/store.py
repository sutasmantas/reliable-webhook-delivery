"""SQLite action state and append-only attempt receipts."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

from deliveryguard.identifiers import payload_hash, validate_idempotency_key
from deliveryguard.models import (
    ActionRecord,
    ActionState,
    AttemptReceipt,
    Classification,
    DeliveryFailure,
    DeliveryResult,
)
from deliveryguard.redaction import redact


class DeliveryStateError(ValueError):
    pass


class IdempotencyConflict(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DeliveryStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS delivery_actions (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    destination TEXT NOT NULL,
                    state TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    cycle INTEGER NOT NULL,
                    last_classification TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS delivery_attempts (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id TEXT NOT NULL REFERENCES delivery_actions(id),
                    cycle INTEGER NOT NULL,
                    cycle_attempt INTEGER NOT NULL,
                    classification TEXT NOT NULL,
                    retryable INTEGER NOT NULL,
                    http_status INTEGER,
                    latency_ms REAL NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    error TEXT,
                    correlation_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(action_id, cycle, cycle_attempt)
                );
                """
            )

    def register(
        self,
        *,
        idempotency_key: str,
        destination: str,
        payload: Mapping[str, Any],
        correlation_id: str,
        max_attempts: int,
    ) -> tuple[ActionRecord, bool]:
        key = validate_idempotency_key(idempotency_key)
        if not destination.strip():
            raise ValueError("Destination is required.")
        if max_attempts < 1 or max_attempts > 10:
            raise ValueError("max_attempts must be between 1 and 10.")
        safe_request = redact(dict(payload))
        if not isinstance(safe_request, dict):
            raise ValueError("Payload must be a JSON object.")
        digest = payload_hash(payload)
        now = _now()
        action_id = str(uuid.uuid4())
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO delivery_actions (
                        id, idempotency_key, destination, state, correlation_id,
                        payload_hash, request_json, attempt_count, max_attempts,
                        cycle, created_at, updated_at
                    ) VALUES (?, ?, ?, 'pending', ?, ?, ?, 0, ?, 1, ?, ?)
                    """,
                    (
                        action_id,
                        key,
                        destination,
                        correlation_id,
                        digest,
                        json.dumps(safe_request, sort_keys=True),
                        max_attempts,
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.get_by_key(key)
            if existing.destination != destination or existing.payload_hash != digest:
                raise IdempotencyConflict(
                    "Idempotency key is already bound to a different destination or payload."
                ) from None
            return existing, False
        return self.get(action_id), True

    def get(self, action_id: str) -> ActionRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM delivery_actions WHERE id = ?", (action_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown delivery action: {action_id}")
        return self._action(row)

    def get_by_key(self, idempotency_key: str) -> ActionRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM delivery_actions WHERE idempotency_key = ?",
                (validate_idempotency_key(idempotency_key),),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown idempotency key: {idempotency_key}")
        return self._action(row)

    def start_attempt(self, action_id: str) -> ActionRecord:
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM delivery_actions WHERE id = ?", (action_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown delivery action: {action_id}")
            current = self._action(row)
            if current.state not in {ActionState.PENDING, ActionState.RETRYING}:
                raise DeliveryStateError(
                    f"Cannot start an attempt from state {current.state.value}."
                )
            if current.attempt_count >= current.max_attempts:
                raise DeliveryStateError("The current retry budget is exhausted.")
            connection.execute(
                """
                UPDATE delivery_actions
                SET state = 'running', attempt_count = attempt_count + 1, updated_at = ?
                WHERE id = ?
                """,
                (now, action_id),
            )
        return self.get(action_id)

    def record_success(
        self,
        action_id: str,
        result: DeliveryResult,
        *,
        latency_ms: float,
    ) -> ActionRecord:
        action = self.get(action_id)
        if action.state is not ActionState.RUNNING:
            raise DeliveryStateError("Only a running action can record success.")
        state = (
            ActionState.ALREADY_APPLIED
            if result.classification is Classification.ALREADY_APPLIED
            else ActionState.DELIVERED
        )
        with self._connect() as connection:
            self._insert_attempt(
                connection,
                action,
                classification=result.classification,
                retryable=False,
                http_status=result.http_status,
                latency_ms=latency_ms,
                response=result.response,
                error=None,
            )
            connection.execute(
                """
                UPDATE delivery_actions
                SET state = ?, last_classification = ?, last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (state.value, result.classification.value, _now(), action_id),
            )
        return self.get(action_id)

    def record_failure(
        self,
        action_id: str,
        failure: DeliveryFailure,
        *,
        latency_ms: float,
    ) -> ActionRecord:
        action = self.get(action_id)
        if action.state is not ActionState.RUNNING:
            raise DeliveryStateError("Only a running action can record failure.")
        terminal = not failure.retryable or action.attempt_count >= action.max_attempts
        state = ActionState.DEAD_LETTER if terminal else ActionState.RETRYING
        safe_evidence = redact(failure.evidence)
        response = safe_evidence if isinstance(safe_evidence, dict) else {}
        with self._connect() as connection:
            self._insert_attempt(
                connection,
                action,
                classification=failure.classification,
                retryable=failure.retryable,
                http_status=failure.http_status,
                latency_ms=latency_ms,
                response=response,
                error=str(failure),
            )
            connection.execute(
                """
                UPDATE delivery_actions
                SET state = ?, last_classification = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    state.value,
                    failure.classification.value,
                    str(failure),
                    _now(),
                    action_id,
                ),
            )
        return self.get(action_id)

    def replay(self, action_id: str, *, correlation_id: str) -> ActionRecord:
        current = self.get(action_id)
        if current.state is not ActionState.DEAD_LETTER:
            raise DeliveryStateError("Only a dead-letter action can be replayed.")
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE delivery_actions
                SET state = 'pending', correlation_id = ?, attempt_count = 0,
                    cycle = cycle + 1, last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (correlation_id, _now(), action_id),
            )
        return self.get(action_id)

    def recover_interrupted(self, action_id: str) -> ActionRecord:
        current = self.get(action_id)
        if current.state is not ActionState.RUNNING:
            return current
        state = (
            ActionState.DEAD_LETTER
            if current.attempt_count >= current.max_attempts
            else ActionState.RETRYING
        )
        with self._connect() as connection:
            self._insert_attempt(
                connection,
                current,
                classification=Classification.WORKER_INTERRUPTED,
                retryable=True,
                http_status=None,
                latency_ms=0.0,
                response={},
                error="Worker interrupted before receipt.",
            )
            connection.execute(
                """
                UPDATE delivery_actions
                SET state = ?, last_error = 'Worker interrupted before receipt.', updated_at = ?
                WHERE id = ?
                """,
                (state.value, _now(), action_id),
            )
        return self.get(action_id)

    def attempts(self, action_id: str) -> list[AttemptReceipt]:
        self.get(action_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM delivery_attempts WHERE action_id = ? ORDER BY sequence",
                (action_id,),
            ).fetchall()
        return [self._attempt(row) for row in rows]

    def _insert_attempt(
        self,
        connection: sqlite3.Connection,
        action: ActionRecord,
        *,
        classification: Classification,
        retryable: bool,
        http_status: int | None,
        latency_ms: float,
        response: Mapping[str, Any],
        error: str | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO delivery_attempts (
                action_id, cycle, cycle_attempt, classification, retryable,
                http_status, latency_ms, request_json, response_json, error,
                correlation_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action.id,
                action.cycle,
                action.attempt_count,
                classification.value,
                int(retryable),
                http_status,
                max(0.0, latency_ms),
                json.dumps(action.request, sort_keys=True),
                json.dumps(dict(response), sort_keys=True),
                error,
                action.correlation_id,
                _now(),
            ),
        )

    @staticmethod
    def _action(row: sqlite3.Row) -> ActionRecord:
        classification = row["last_classification"]
        return ActionRecord(
            id=cast("str", row["id"]),
            idempotency_key=cast("str", row["idempotency_key"]),
            destination=cast("str", row["destination"]),
            state=ActionState(row["state"]),
            correlation_id=cast("str", row["correlation_id"]),
            payload_hash=cast("str", row["payload_hash"]),
            request=cast("dict[str, Any]", json.loads(row["request_json"])),
            attempt_count=cast("int", row["attempt_count"]),
            max_attempts=cast("int", row["max_attempts"]),
            cycle=cast("int", row["cycle"]),
            last_classification=Classification(classification)
            if classification
            else None,
            last_error=cast("str | None", row["last_error"]),
            created_at=cast("str", row["created_at"]),
            updated_at=cast("str", row["updated_at"]),
        )

    @staticmethod
    def _attempt(row: sqlite3.Row) -> AttemptReceipt:
        return AttemptReceipt(
            sequence=cast("int", row["sequence"]),
            action_id=cast("str", row["action_id"]),
            cycle=cast("int", row["cycle"]),
            cycle_attempt=cast("int", row["cycle_attempt"]),
            classification=Classification(row["classification"]),
            retryable=bool(row["retryable"]),
            http_status=cast("int | None", row["http_status"]),
            latency_ms=cast("float", row["latency_ms"]),
            request=cast("dict[str, Any]", json.loads(row["request_json"])),
            response=cast("dict[str, Any]", json.loads(row["response_json"])),
            error=cast("str | None", row["error"]),
            correlation_id=cast("str", row["correlation_id"]),
            created_at=cast("str", row["created_at"]),
        )
