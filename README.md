# DeliveryGuard

DeliveryGuard is a small Python delivery boundary for webhook and tool actions.
It turns transport outcomes into durable, inspectable behavior: stable
idempotency keys, bounded retries, append-only attempt receipts, dead letters,
and explicit replay.

It is built on the retry controller from
[Tenacity](https://github.com/jd/tenacity). The portfolio-owned layer adds the
delivery state machine, SQLite evidence, webhook normalization, secret
references, redaction, conformance fixtures, and a credential-free lifecycle
demo. See [THIRD_PARTY_REUSE.md](THIRD_PARTY_REUSE.md) for the exact boundary.

![DeliveryGuard recovery console](docs/screenshots/deliveryguard-console-1600.png)

## Quickstart

```bash
python -m venv .venv
# Windows: .venv\Scripts\python -m pip install -e ".[test]"
# macOS/Linux: .venv/bin/python -m pip install -e ".[test]"
.venv\Scripts\python -m pytest tests/test_deliveryguard.py
.venv\Scripts\deliveryguard demo --database .demo/delivery.sqlite3
```

The demo must print `"gate": "PASS"`. It proves a transient failure retries to
success, a duplicate does not call the adapter again, a permanent failure moves
to dead letter, replay starts a new cycle, and configured secret fields do not
enter receipts.

## Run the recovery console

The local browser console executes that same demo and renders its real SQLite
receipts. It does not need an API key or external endpoint.

```bash
.venv\Scripts\deliveryguard-viewer
# open http://127.0.0.1:8768
```

Select an attempt to inspect its classification and sanitized receipt, or run
the proof again to create a fresh lifecycle. The console makes the important
delivery decisions visible: bounded retry, duplicate suppression, terminal
dead letter, explicit replay, and secret redaction.

The Upwork-ready screenshots and 18-second walkthrough are in
[`final_upload/`](final_upload/). Rebuild them with
[`scripts/capture_publication.py`](scripts/capture_publication.py).

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

## Boundaries

DeliveryGuard does not claim distributed exactly-once delivery, production
scale, multi-tenant authorization, endpoint trust/SSRF enforcement, or support
for a named SaaS provider. It provides at-least-once attempts guarded by an
idempotency contract; the destination must honor that contract for duplicate
side effects to be prevented across network ambiguity.
