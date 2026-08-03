"""Bounded delivery execution powered by Tenacity retry state."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from deliveryguard.identifiers import normalize_correlation_id
from deliveryguard.models import (
    ActionRecord,
    ActionState,
    Classification,
    DeliveryFailure,
    DeliveryResult,
)
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_fixed

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from deliveryguard.store import DeliveryStore


class DeliveryAdapter(Protocol):
    def send(
        self,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        correlation_id: str,
    ) -> DeliveryResult: ...


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    wait_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.max_attempts > 10:
            raise ValueError("max_attempts must be between 1 and 10.")
        if self.wait_seconds < 0 or self.wait_seconds > 60:
            raise ValueError("wait_seconds must be between 0 and 60.")


class DeliveryExecutor:
    def __init__(
        self,
        store: DeliveryStore,
        adapter: DeliveryAdapter,
        *,
        policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.store = store
        self.adapter = adapter
        self.policy = policy or RetryPolicy()
        self._sleeper = sleeper
        self._clock = clock

    def deliver(
        self,
        *,
        idempotency_key: str,
        destination: str,
        payload: Mapping[str, Any],
        correlation_id: str | None = None,
    ) -> ActionRecord:
        correlation = normalize_correlation_id(correlation_id)
        action, created = self.store.register(
            idempotency_key=idempotency_key,
            destination=destination,
            payload=payload,
            correlation_id=correlation,
            max_attempts=self.policy.max_attempts,
        )
        if not created and action.state in {
            ActionState.DELIVERED,
            ActionState.ALREADY_APPLIED,
            ActionState.DEAD_LETTER,
        }:
            return action
        if action.state is ActionState.RUNNING:
            action = self.store.recover_interrupted(action.id)
        if action.state is ActionState.DEAD_LETTER:
            return action

        remaining = action.max_attempts - action.attempt_count
        retryer = Retrying(
            stop=stop_after_attempt(remaining),
            wait=wait_fixed(self.policy.wait_seconds),
            retry=retry_if_exception(
                lambda exc: isinstance(exc, DeliveryFailure) and exc.retryable
            ),
            sleep=self._sleeper,
            reraise=True,
        )
        try:
            for attempt in retryer:
                with attempt:
                    running = self.store.start_attempt(action.id)
                    started = self._clock()
                    try:
                        result = self.adapter.send(
                            payload,
                            idempotency_key=running.idempotency_key,
                            correlation_id=running.correlation_id,
                        )
                    except DeliveryFailure as caught:
                        self.store.record_failure(
                            running.id,
                            caught,
                            latency_ms=(self._clock() - started) * 1000,
                        )
                        raise
                    except Exception as exc:
                        normalized = DeliveryFailure(
                            Classification.MALFORMED_RESPONSE,
                            f"Adapter raised unnormalized {type(exc).__name__}.",
                            retryable=False,
                        )
                        self.store.record_failure(
                            running.id,
                            normalized,
                            latency_ms=(self._clock() - started) * 1000,
                        )
                        raise normalized from None
                    else:
                        return self.store.record_success(
                            running.id,
                            result,
                            latency_ms=(self._clock() - started) * 1000,
                        )
        except DeliveryFailure:
            return self.store.get(action.id)
        raise RuntimeError("Delivery retry loop ended without a durable outcome.")

    def replay(
        self,
        action_id: str,
        *,
        payload: Mapping[str, Any],
        correlation_id: str | None = None,
    ) -> ActionRecord:
        replayed = self.store.replay(
            action_id,
            correlation_id=normalize_correlation_id(correlation_id),
        )
        return self.deliver(
            idempotency_key=replayed.idempotency_key,
            destination=replayed.destination,
            payload=payload,
            correlation_id=replayed.correlation_id,
        )
