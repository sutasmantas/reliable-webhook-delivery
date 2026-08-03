"""Credential-free DeliveryGuard smoke demonstration."""

from __future__ import annotations

import argparse
import json
import uuid
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

from deliveryguard.executor import DeliveryExecutor, RetryPolicy
from deliveryguard.models import (
    ActionRecord,
    Classification,
    DeliveryFailure,
    DeliveryResult,
)
from deliveryguard.store import DeliveryStore


class ScriptedAdapter:
    def __init__(self, outcomes: Sequence[DeliveryResult | DeliveryFailure]) -> None:
        self.outcomes = deque(outcomes)
        self.calls = 0

    def send(
        self,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        correlation_id: str,
    ) -> DeliveryResult:
        del payload, idempotency_key, correlation_id
        self.calls += 1
        if not self.outcomes:
            raise RuntimeError("Scripted adapter has no remaining outcome.")
        outcome = self.outcomes.popleft()
        if isinstance(outcome, DeliveryFailure):
            raise outcome
        return outcome


def _record(record: ActionRecord) -> dict[str, Any]:
    return {
        "state": record.state.value,
        "attempt_count": record.attempt_count,
        "cycle": record.cycle,
        "classification": (
            record.last_classification.value if record.last_classification else None
        ),
    }


def _receipt(receipt: Any) -> dict[str, Any]:
    return {
        "sequence": receipt.sequence,
        "cycle": receipt.cycle,
        "attempt": receipt.cycle_attempt,
        "classification": receipt.classification.value,
        "retryable": receipt.retryable,
        "http_status": receipt.http_status,
        "request": receipt.request,
        "response": receipt.response,
        "error": receipt.error,
        "correlation_id": receipt.correlation_id,
    }


def run_demo(database: Path) -> dict[str, Any]:
    store = DeliveryStore(database)
    run_id = uuid.uuid4().hex[:12]
    transient_adapter = ScriptedAdapter(
        [
            DeliveryFailure(
                Classification.SERVER_ERROR,
                "Scripted server error.",
                retryable=True,
                http_status=503,
            ),
            DeliveryResult(Classification.SUCCESS, 202, {"receipt": "demo-accepted"}),
        ]
    )
    executor = DeliveryExecutor(
        store,
        transient_adapter,
        policy=RetryPolicy(max_attempts=2),
    )
    payload = {"event": "demo.delivery", "token": "must-not-persist"}
    delivered = executor.deliver(
        idempotency_key=f"demo:transient-{run_id}",
        destination="scripted://transient",
        payload=payload,
        correlation_id="demo-request-0001",
    )
    duplicate = executor.deliver(
        idempotency_key=f"demo:transient-{run_id}",
        destination="scripted://transient",
        payload=payload,
        correlation_id="ignored-duplicate-request",
    )

    failed_adapter = ScriptedAdapter(
        [
            DeliveryFailure(
                Classification.CLIENT_ERROR,
                "Scripted request rejection.",
                retryable=False,
                http_status=422,
            )
        ]
    )
    failed_executor = DeliveryExecutor(store, failed_adapter)
    dead_letter = failed_executor.deliver(
        idempotency_key=f"demo:dead-{run_id}",
        destination="scripted://permanent",
        payload={"event": "demo.invalid"},
        correlation_id="demo-request-0002",
    )
    replay_executor = DeliveryExecutor(
        store,
        ScriptedAdapter([DeliveryResult(Classification.SUCCESS, 200, {})]),
    )
    replayed = replay_executor.replay(
        dead_letter.id,
        payload={"event": "demo.invalid"},
        correlation_id="demo-request-0003",
    )
    transient_attempts = store.attempts(delivered.id)
    replay_attempts = store.attempts(replayed.id)
    secret_value_persisted = "must-not-persist" in database.read_bytes().decode(
        "utf-8", errors="ignore"
    )
    gate = (
        delivered.state.value == "delivered"
        and len(transient_attempts) == 2
        and duplicate.id == delivered.id
        and transient_adapter.calls == 2
        and dead_letter.state.value == "dead_letter"
        and replayed.state.value == "delivered"
        and replayed.cycle == 2
        and len(replay_attempts) == 2
        and not secret_value_persisted
    )
    return {
        "gate": "PASS" if gate else "FAIL",
        "transient_then_success": _record(delivered),
        "duplicate_reused_action": duplicate.id == delivered.id,
        "dead_letter_before_replay": _record(dead_letter),
        "after_replay": _record(replayed),
        "attempt_classifications": [
            receipt.classification.value
            for receipt in transient_attempts + replay_attempts
        ],
        "timeline": [
            _receipt(receipt) for receipt in transient_attempts + replay_attempts
        ],
        "summary": {
            "unique_actions": 2,
            "transport_attempts": len(transient_attempts) + len(replay_attempts),
            "retry_recovered": delivered.state.value == "delivered",
            "duplicate_transport_calls": transient_adapter.calls - 2,
            "dead_letters_before_replay": 1,
            "replayed_cycles": replayed.cycle - 1,
        },
        "secret_value_persisted": secret_value_persisted,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="deliveryguard")
    commands = result.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="run the deterministic delivery lifecycle")
    demo.add_argument(
        "--database",
        type=Path,
        default=Path("deliveryguard-demo.sqlite3"),
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.command == "demo":
        output = run_demo(arguments.database)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0 if output["gate"] == "PASS" else 1
    raise RuntimeError("Unknown command.")


if __name__ == "__main__":
    raise SystemExit(main())
