"""Frozen HTTP and network outcome normalization."""

from __future__ import annotations

from deliveryguard.models import Classification, DeliveryFailure


def failure_for_http_status(status: int) -> DeliveryFailure:
    if status == 429:
        return DeliveryFailure(
            Classification.RATE_LIMIT,
            "Delivery endpoint is rate limited.",
            retryable=True,
            http_status=status,
        )
    if 500 <= status <= 599:
        return DeliveryFailure(
            Classification.SERVER_ERROR,
            "Delivery endpoint returned a server error.",
            retryable=True,
            http_status=status,
        )
    return DeliveryFailure(
        Classification.CLIENT_ERROR,
        "Delivery endpoint rejected the request.",
        retryable=False,
        http_status=status,
    )
