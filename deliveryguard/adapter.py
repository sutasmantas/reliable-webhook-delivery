"""A generic webhook adapter with normalized, secret-safe outcomes."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, Self, cast
from urllib.parse import urlparse

from deliveryguard.classification import failure_for_http_status
from deliveryguard.models import Classification, DeliveryFailure, DeliveryResult
from deliveryguard.redaction import DEFAULT_REDACTED_FIELDS, redact
from deliveryguard.secrets import EnvironmentSecretResolver, SecretResolutionError


class ResponseLike(Protocol):
    status: int

    def read(self) -> bytes: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *args: object) -> None: ...


OpenRequest = Callable[[urllib.request.Request, float], ResponseLike]


@dataclass(frozen=True)
class ProviderConfig:
    url: str
    secret_ref: str | None = None
    secret_header: str = "Authorization"
    secret_prefix: str = "Bearer "
    idempotency_header: str = "Idempotency-Key"
    correlation_header: str = "X-Request-ID"
    timeout_seconds: float = 10.0
    redacted_fields: frozenset[str] = field(default=DEFAULT_REDACTED_FIELDS)

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Provider URL must be an absolute HTTP(S) URL.")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 120:
            raise ValueError(
                "Timeout must be greater than zero and no more than 120 seconds."
            )
        for header in (
            self.secret_header,
            self.idempotency_header,
            self.correlation_header,
        ):
            if not header.strip() or "\n" in header or "\r" in header:
                raise ValueError("Header names must be non-empty single-line values.")


class WebhookAdapter:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        opener: OpenRequest | None = None,
        secret_resolver: EnvironmentSecretResolver | None = None,
    ) -> None:
        self.config = config
        self._opener = opener or self._open
        self._secret_resolver = secret_resolver or EnvironmentSecretResolver()

    @staticmethod
    def _open(request: urllib.request.Request, timeout: float) -> ResponseLike:
        return cast("ResponseLike", urllib.request.urlopen(request, timeout=timeout))

    def send(
        self,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        correlation_id: str,
    ) -> DeliveryResult:
        headers = {
            "Content-Type": "application/json",
            self.config.idempotency_header: idempotency_key,
            self.config.correlation_header: correlation_id,
        }
        if self.config.secret_ref:
            try:
                secret = self._secret_resolver.resolve(self.config.secret_ref)
            except SecretResolutionError as exc:
                raise DeliveryFailure(
                    Classification.CONFIGURATION_ERROR,
                    str(exc),
                    retryable=False,
                ) from None
            headers[self.config.secret_header] = f"{self.config.secret_prefix}{secret}"
        request = urllib.request.Request(
            self.config.url,
            data=json.dumps(payload, sort_keys=True).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with self._opener(request, self.config.timeout_seconds) as response:
                body = response.read()
                return self._success(response.status, body)
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                return DeliveryResult(
                    Classification.ALREADY_APPLIED,
                    http_status=exc.code,
                    response={},
                )
            raise failure_for_http_status(exc.code) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DeliveryFailure(
                Classification.NETWORK_ERROR,
                f"Delivery endpoint could not be reached ({type(exc).__name__}).",
                retryable=True,
            ) from None

    def _success(self, status: int, body: bytes) -> DeliveryResult:
        if status == 409:
            return DeliveryResult(Classification.ALREADY_APPLIED, status, {})
        if not 200 <= status <= 299:
            raise failure_for_http_status(status)
        if not body:
            response: dict[str, Any] = {}
        else:
            try:
                parsed = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise DeliveryFailure(
                    Classification.MALFORMED_RESPONSE,
                    "Delivery endpoint returned malformed JSON.",
                    retryable=False,
                    http_status=status,
                ) from None
            if not isinstance(parsed, dict):
                raise DeliveryFailure(
                    Classification.MALFORMED_RESPONSE,
                    "Delivery endpoint response must be a JSON object.",
                    retryable=False,
                    http_status=status,
                )
            response = cast(
                "dict[str, Any]", redact(parsed, self.config.redacted_fields)
            )
        return DeliveryResult(Classification.SUCCESS, status, response)
