# DeliveryGuard

DeliveryGuard makes webhook and tool delivery recoverable and inspectable. It
turns transport outcomes into durable behavior: stable
idempotency keys, bounded retries, append-only attempt receipts, dead letters,
and explicit replay.

![DeliveryGuard recovery console](docs/screenshots/deliveryguard-console-1600.png)

[Open the live recovery console](https://sutasmantas.github.io/reliable-webhook-delivery/)

## Quickstart

```bash
python -m venv .venv
# Windows: .venv\Scripts\python -m pip install -e ".[test]"
# macOS/Linux: .venv/bin/python -m pip install -e ".[test]"
.venv\Scripts\python -m pytest tests/test_deliveryguard.py
.venv\Scripts\deliveryguard demo --database .demo/delivery.sqlite3
```

The command must print `"gate": "PASS"`. It proves a transient failure retries to
success, a duplicate does not call the adapter again, a permanent failure moves
to dead letter, replay starts a new cycle, and configured secret fields do not
enter receipts.

## Run the recovery console

The local browser console executes the same lifecycle and renders its real SQLite
receipts. It does not need an API key or external endpoint.

```bash
.venv\Scripts\deliveryguard-viewer
# open http://127.0.0.1:8768
```

Select an attempt to inspect its classification and sanitized receipt, or run
the proof again to create a fresh lifecycle. The console makes the important
delivery decisions visible: bounded retry, duplicate suppression, terminal
dead letter, explicit replay, and secret redaction.

## Minimal use

```python
from deliveryguard import DeliveryExecutor, DeliveryStore, ProviderConfig, WebhookAdapter

store = DeliveryStore("delivery.sqlite3")
adapter = WebhookAdapter(
    ProviderConfig(
        "https://client.example/webhooks/actions",
        secret_ref="env:CLIENT_WEBHOOK_TOKEN",
    )
)
executor = DeliveryExecutor(store, adapter)
receipt = executor.deliver(
    idempotency_key="ticket:CS-123:notify",
    destination="client-actions",
    payload={"event": "ticket.resolved", "ticket_id": "CS-123"},
)
print(receipt.state.value)
```
