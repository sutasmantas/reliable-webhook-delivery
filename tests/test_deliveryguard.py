from __future__ import annotations

import json
import urllib.error
import urllib.request
from importlib.resources import files
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Mapping

import pytest

from deliveryguard.adapter import ProviderConfig, WebhookAdapter
from deliveryguard.classification import failure_for_http_status
from deliveryguard.cli import ScriptedAdapter, run_demo
from deliveryguard.executor import DeliveryExecutor, RetryPolicy
from deliveryguard.identifiers import make_idempotency_key, normalize_correlation_id
from deliveryguard.models import (
    ActionState,
    Classification,
    DeliveryFailure,
    DeliveryResult,
)
from deliveryguard.redaction import REDACTED, redact
from deliveryguard.secrets import EnvironmentSecretResolver, SecretResolutionError
from deliveryguard.store import DeliveryStateError, DeliveryStore, IdempotencyConflict
from deliveryguard.viewer_server import create_viewer_server

FIXTURES = Path(__file__).parent / "fixtures" / "delivery_conformance.json"


def test_package_exposes_py_typed_marker() -> None:
    assert files("deliveryguard").joinpath("py.typed").is_file()


class FakeResponse:
    def __init__(self, status: int, body: bytes = b"{}") -> None:
        self.status = status
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def executor(
    tmp_path: Path,
    outcomes: list[DeliveryResult | DeliveryFailure],
    *,
    max_attempts: int = 3,
) -> tuple[DeliveryStore, ScriptedAdapter, DeliveryExecutor]:
    store = DeliveryStore(tmp_path / "delivery.sqlite3")
    adapter = ScriptedAdapter(outcomes)
    delivery = DeliveryExecutor(
        store,
        adapter,
        policy=RetryPolicy(max_attempts=max_attempts),
        sleeper=lambda _: None,
    )
    return store, adapter, delivery


def test_frozen_http_conformance_vectors() -> None:
    vectors = json.loads(FIXTURES.read_text(encoding="utf-8"))
    for vector in vectors:
        status = vector["status"]
        if 200 <= status <= 299 or status == 409:

            def opener(
                request: Any, timeout: float, status_code: int = status
            ) -> FakeResponse:
                del request, timeout
                if status_code == 409:
                    raise urllib.error.HTTPError(
                        "https://example.test/hook", status_code, "conflict", {}, None
                    )
                return FakeResponse(status_code)

            result = WebhookAdapter(
                ProviderConfig("https://example.test/hook"), opener=opener
            ).send(
                {},
                idempotency_key="test:conformance-vector",
                correlation_id="request-12345678",
            )
            assert result.classification.value == vector["classification"]
        else:
            failure = failure_for_http_status(status)
            assert failure.classification.value == vector["classification"]
            assert failure.retryable is vector["retryable"]


def test_transient_failure_retries_and_persists_receipts(tmp_path: Path) -> None:
    store, adapter, delivery = executor(
        tmp_path,
        [
            DeliveryFailure(
                Classification.RATE_LIMIT,
                "busy",
                retryable=True,
                http_status=429,
            ),
            DeliveryResult(Classification.SUCCESS, 202, {"receipt": "ok"}),
        ],
    )
    action = delivery.deliver(
        idempotency_key="test:transient-action",
        destination="https://example.test/hook",
        payload={"event": "created"},
        correlation_id="request-12345678",
    )
    receipts = store.attempts(action.id)
    assert action.state is ActionState.DELIVERED
    assert adapter.calls == 2
    assert [item.classification for item in receipts] == [
        Classification.RATE_LIMIT,
        Classification.SUCCESS,
    ]
    assert [item.cycle_attempt for item in receipts] == [1, 2]


def test_retry_budget_exhausts_to_dead_letter(tmp_path: Path) -> None:
    store, adapter, delivery = executor(
        tmp_path,
        [
            DeliveryFailure(Classification.SERVER_ERROR, "down", retryable=True),
            DeliveryFailure(Classification.SERVER_ERROR, "down", retryable=True),
        ],
        max_attempts=2,
    )
    action = delivery.deliver(
        idempotency_key="test:exhausted-action",
        destination="scripted://down",
        payload={"event": "created"},
    )
    assert action.state is ActionState.DEAD_LETTER
    assert action.attempt_count == 2
    assert adapter.calls == 2
    assert len(store.attempts(action.id)) == 2


def test_terminal_failure_does_not_retry(tmp_path: Path) -> None:
    store, adapter, delivery = executor(
        tmp_path,
        [DeliveryFailure(Classification.CLIENT_ERROR, "invalid", retryable=False)],
    )
    action = delivery.deliver(
        idempotency_key="test:terminal-action",
        destination="scripted://invalid",
        payload={"event": "invalid"},
    )
    assert action.state is ActionState.DEAD_LETTER
    assert adapter.calls == 1
    assert len(store.attempts(action.id)) == 1


def test_duplicate_terminal_action_is_reused_without_transport(tmp_path: Path) -> None:
    store, adapter, delivery = executor(
        tmp_path, [DeliveryResult(Classification.SUCCESS, 200, {})]
    )
    arguments: dict[str, Any] = {
        "idempotency_key": "test:duplicate-action",
        "destination": "scripted://success",
        "payload": {"event": "created"},
    }
    first = delivery.deliver(**arguments)
    second = delivery.deliver(**arguments)
    assert second.id == first.id
    assert adapter.calls == 1
    assert len(store.attempts(first.id)) == 1


def test_idempotency_collision_refuses_changed_payload(tmp_path: Path) -> None:
    _, _, delivery = executor(
        tmp_path, [DeliveryResult(Classification.SUCCESS, 200, {})]
    )
    delivery.deliver(
        idempotency_key="test:collision-action",
        destination="scripted://success",
        payload={"version": 1},
    )
    with pytest.raises(IdempotencyConflict):
        delivery.deliver(
            idempotency_key="test:collision-action",
            destination="scripted://success",
            payload={"version": 2},
        )


def test_dead_letter_replay_starts_new_cycle_and_keeps_history(tmp_path: Path) -> None:
    store, _, failed = executor(
        tmp_path,
        [DeliveryFailure(Classification.CLIENT_ERROR, "invalid", retryable=False)],
    )
    payload = {"event": "created"}
    dead = failed.deliver(
        idempotency_key="test:replay-action",
        destination="scripted://repairable",
        payload=payload,
    )
    success = DeliveryExecutor(
        store,
        ScriptedAdapter([DeliveryResult(Classification.SUCCESS, 200, {})]),
    )
    replayed = success.replay(dead.id, payload=payload)
    receipts = store.attempts(dead.id)
    assert replayed.state is ActionState.DELIVERED
    assert replayed.cycle == 2
    assert [(item.cycle, item.cycle_attempt) for item in receipts] == [(1, 1), (2, 1)]
    with pytest.raises(DeliveryStateError):
        store.replay(replayed.id, correlation_id="request-87654321")


def test_interrupted_attempt_is_recovered_without_erasing_budget(
    tmp_path: Path,
) -> None:
    store = DeliveryStore(tmp_path / "delivery.sqlite3")
    action, _ = store.register(
        idempotency_key="test:interrupted-action",
        destination="scripted://worker",
        payload={"event": "created"},
        correlation_id="request-12345678",
        max_attempts=2,
    )
    running = store.start_attempt(action.id)
    recovered = store.recover_interrupted(running.id)
    assert recovered.state is ActionState.RETRYING
    assert recovered.attempt_count == 1
    receipts = store.attempts(action.id)
    assert len(receipts) == 1
    assert receipts[0].classification is Classification.WORKER_INTERRUPTED


def test_missing_webhook_secret_is_terminal_configuration_failure() -> None:
    adapter = WebhookAdapter(
        ProviderConfig(
            "https://example.test/hook",
            secret_ref="env:MISSING_DELIVERYGUARD_SECRET",
        )
    )
    with pytest.raises(DeliveryFailure) as caught:
        adapter.send(
            {},
            idempotency_key="test:missing-secret",
            correlation_id="request-12345678",
        )
    assert caught.value.classification is Classification.CONFIGURATION_ERROR
    assert caught.value.retryable is False


def test_webhook_headers_secret_reference_and_redacted_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DELIVERYGUARD_TEST_TOKEN", "never-persist-this")
    captured: dict[str, Any] = {}

    def opener(request: Any, timeout: float) -> FakeResponse:
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeResponse(202, b'{"token":"response-secret","receipt":"ok"}')

    adapter = WebhookAdapter(
        ProviderConfig(
            "https://example.test/hook",
            secret_ref="env:DELIVERYGUARD_TEST_TOKEN",
        ),
        opener=opener,
    )
    result = adapter.send(
        {"event": "created"},
        idempotency_key="test:webhook-action",
        correlation_id="request-12345678",
    )
    assert result.classification is Classification.SUCCESS
    assert result.response == {"token": REDACTED, "receipt": "ok"}
    assert captured["headers"]["Idempotency-key"] == "test:webhook-action"
    assert captured["headers"]["X-request-id"] == "request-12345678"
    assert captured["headers"]["Authorization"] == "Bearer never-persist-this"
    assert captured["timeout"] == 10.0


@pytest.mark.parametrize(
    ("status", "classification", "retryable"),
    [
        (409, Classification.ALREADY_APPLIED, False),
        (429, Classification.RATE_LIMIT, True),
        (503, Classification.SERVER_ERROR, True),
        (422, Classification.CLIENT_ERROR, False),
    ],
)
def test_webhook_http_outcomes(
    status: int,
    classification: Classification,
    retryable: bool,
) -> None:
    def opener(request: Any, timeout: float) -> FakeResponse:
        del request, timeout
        raise urllib.error.HTTPError(
            "https://example.test/hook", status, "failure", {}, None
        )

    adapter = WebhookAdapter(ProviderConfig("https://example.test/hook"), opener=opener)
    if status == 409:
        result = adapter.send(
            {}, idempotency_key="test:http-conflict", correlation_id="request-12345678"
        )
        assert result.classification is classification
    else:
        with pytest.raises(DeliveryFailure) as caught:
            adapter.send(
                {},
                idempotency_key="test:http-failure",
                correlation_id="request-12345678",
            )
        assert caught.value.classification is classification
        assert caught.value.retryable is retryable


def test_malformed_success_response_is_terminal() -> None:
    adapter = WebhookAdapter(
        ProviderConfig("https://example.test/hook"),
        opener=lambda request, timeout: FakeResponse(200, b"not-json"),
    )
    with pytest.raises(DeliveryFailure) as caught:
        adapter.send(
            {},
            idempotency_key="test:malformed-action",
            correlation_id="request-12345678",
        )
    assert caught.value.classification is Classification.MALFORMED_RESPONSE
    assert caught.value.retryable is False


def test_identifiers_redaction_and_secret_reference_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = make_idempotency_key("handoff", {"b": 2, "a": 1})
    second = make_idempotency_key("handoff", {"a": 1, "b": 2})
    assert first == second
    assert normalize_correlation_id("bad") != "bad"
    assert redact({"nested": {"password": "secret", "safe": "yes"}}) == {
        "nested": {"password": REDACTED, "safe": "yes"}
    }
    resolver = EnvironmentSecretResolver()
    monkeypatch.delenv("MISSING_DELIVERY_TOKEN", raising=False)
    with pytest.raises(SecretResolutionError):
        resolver.resolve("env:MISSING_DELIVERY_TOKEN")
    with pytest.raises(SecretResolutionError):
        resolver.resolve("literal:unsafe")


def test_unexpected_adapter_exception_is_safely_normalized(tmp_path: Path) -> None:
    class BrokenAdapter:
        def send(
            self,
            payload: Mapping[str, Any],
            *,
            idempotency_key: str,
            correlation_id: str,
        ) -> DeliveryResult:
            del payload, idempotency_key, correlation_id
            raise KeyError("raw-provider-secret")

    store = DeliveryStore(tmp_path / "delivery.sqlite3")
    delivery = DeliveryExecutor(store, BrokenAdapter())
    action = delivery.deliver(
        idempotency_key="test:broken-adapter",
        destination="scripted://broken",
        payload={"token": "raw-provider-secret"},
    )
    serialized = json.dumps(store.attempts(action.id)[0].__dict__)
    assert action.state is ActionState.DEAD_LETTER
    assert "raw-provider-secret" not in serialized
    assert "KeyError" in serialized


def test_demo_exercises_retry_dedupe_dead_letter_replay_and_redaction(
    tmp_path: Path,
) -> None:
    output = run_demo(tmp_path / "demo.sqlite3")
    assert output["gate"] == "PASS"
    assert output["duplicate_reused_action"] is True
    assert output["after_replay"]["cycle"] == 2
    assert output["summary"] == {
        "unique_actions": 2,
        "transport_attempts": 4,
        "retry_recovered": True,
        "duplicate_transport_calls": 0,
        "dead_letters_before_replay": 1,
        "replayed_cycles": 1,
    }
    assert [item["classification"] for item in output["timeline"]] == [
        "server_error",
        "success",
        "client_error",
        "success",
    ]


def test_viewer_serves_real_demo_and_static_console(tmp_path: Path) -> None:
    server = create_viewer_server(tmp_path / "viewer.sqlite3", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/demo") as response:
            report = json.loads(response.read())
        assert report["gate"] == "PASS"
        assert report["summary"]["transport_attempts"] == 4
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as response:
            html = response.read().decode("utf-8")
        assert "Recover the delivery" in html
        assert "delivery flight recorder" in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
