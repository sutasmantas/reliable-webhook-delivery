"""Durable delivery contracts built around explicit evidence."""

from deliveryguard.adapter import ProviderConfig, WebhookAdapter
from deliveryguard.executor import DeliveryExecutor, RetryPolicy
from deliveryguard.identifiers import make_idempotency_key, normalize_correlation_id
from deliveryguard.models import (
    ActionRecord,
    ActionState,
    Classification,
    DeliveryFailure,
    DeliveryResult,
)
from deliveryguard.store import DeliveryStore

__all__ = [
    "ActionRecord",
    "ActionState",
    "Classification",
    "DeliveryExecutor",
    "DeliveryFailure",
    "DeliveryResult",
    "DeliveryStore",
    "ProviderConfig",
    "RetryPolicy",
    "WebhookAdapter",
    "make_idempotency_key",
    "normalize_correlation_id",
]
