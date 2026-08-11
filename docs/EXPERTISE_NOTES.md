# Retry only normalized transient outcomes

### Client trigger

- Job wording or deliverable that makes this relevant: reliable API/webhook
  integration, retries, idempotency, dead-letter handling, or operational
  handoff
- How often it appeared in the measured corpus or proposal log: deployment
  appeared in 24.6% and reliability/error handling in 21.0% of the measured
  corpus recorded by the depth plan
- Existing project/component that can be reused: DeliveryGuard executor,
  webhook normalizer, and SQLite receipt store

### Failure symptom or unanswered choice

Retrying every exception can duplicate permanent failures and hide invalid
configuration. Not retrying can lose recoverable actions during rate limits,
server failures, or network interruption.

### Competing options

| Option | Why it is plausible | Main cost or failure risk |
| --- | --- | --- |
| Raw retry decorator around a webhook call | minimal implementation | retries permanent 4xx/configuration errors unless every caller recreates classification correctly |
| App-local state and retry code | can match one workflow closely | repeated semantics drift across projects and evidence formats |
| Typed shared delivery contract | central outcome taxonomy, retry predicate, durable receipts, and replay | deliberately narrower than full job orchestration and requires destinations to honor idempotency |

### Controlled comparison

- Representative cases or fixtures: frozen 200, 202, 204, 409, 400, 401,
  422, 429, 500, and 503 vectors plus network, malformed JSON, missing secret,
  interrupted worker, collision, exhaustion, duplicate, and replay tests
- Frozen development/held-out split, when relevant: not applicable; this is a
  deterministic contract suite
- Metrics and decision thresholds chosen before the run: every vector maps to
  the expected class; only transient outcomes retry; every attempt has a
  receipt; duplicates make no second transport call; demo gate must pass
- Runtime, hardware, model/provider version, cost assumptions, and date:
  Python 3.13.5, Tenacity 9.1.4 runtime API against GitHub foundation
  `b3c5a9f`, Windows/Docker Python 3.12, 2026-08-01, no paid provider
- What is deliberately outside the comparison: provider-specific rate-limit
  headers, distributed queues, circuit breakers, and throughput

### Result

All 18 DeliveryGuard tests passed. The retained Tenacity suite plus the new
tests produced 190 passed, 1 skipped, and 12 passed subtests. The deterministic
demo passed natively twice against the same database and in the built Docker
image. A permanent 4xx stopped after one attempt; two transient failures
exhausted exactly at the configured budget; 409 became an idempotent success.

### Decision rule

Use DeliveryGuard for synchronous Python actions that need explicit
idempotency, bounded retry, durable receipts, and manual replay. Re-test or use
a queue-specific system when work is multi-process, high-volume, leased across
workers, or governed by provider-specific retry headers.

### Delivery control

Freeze provider outcome mappings as conformance vectors. Refuse key collisions,
retry only normalized transient classifications, and require dead-letter replay
to be explicit rather than automatic.

### Reuse boundary

- Reusable without client data: identifiers, taxonomy, executor, SQLite store,
  webhook adapter, CLI demo, and tests
- Requires client data, credentials, environment, or acceptance criteria:
  endpoint URL, secret reference, payload mapping, timeout/retry budget, and
  destination idempotency behavior
- Unsupported claim that must not appear in a proposal: exactly-once or
  production-scale delivery

### Proposal-safe insight

I separate retry decisions from provider error text: rate limits, network
failures, and server failures consume a bounded retry budget, while permanent
rejections and configuration errors stop visibly in a replayable dead letter.

### Evidence

- Code: `deliveryguard/adapter.py`, `deliveryguard/executor.py`,
  `deliveryguard/store.py`
- Tests: `tests/test_deliveryguard.py`
- Raw comparison artifacts: `tests/fixtures/delivery_conformance.json`,
  `docs/evidence/demo.json`
- Human review, if used: source inventory against Atlas, Relay, and Website
  Assistant
- Reproduction command: `deliveryguard demo --database .demo/delivery.sqlite3`

### Interview follow-up

- Likely technical question: Does an idempotency key give exactly-once delivery?
- Short answer: No. The sender can make at-least-once attempts safely only when
  the receiving system stores and honors the same key.
- Deeper evidence to open if challenged: duplicate/collision tests, attempt
  receipts, and the 409 already-applied vector
# Systematic technique decisions (2026-08-05)

The original note below remains the implemented local decision. The two notes
here are research-backed operating rules; their D-series experiments have not
run.

## Make the business write and delivery request atomic

- **Trigger:** a committed order, lead, payment or record change must always
  produce a recoverable external notification.
- **Failure:** writing business state and enqueueing/sending separately creates
  a crash window where one commits without the other.
- **Decision:** write a stable outbox event in the same source transaction,
  then publish asynchronously and reconcile by event identity. Use polling by
  default; admit Debezium only for a measured freshness or existing-platform
  advantage.
- **Delivery control:** inject crashes before/after commit and between publish
  and acknowledgement; require no committed business row without a discoverable
  event and no event without committed state.
- **Boundary:** DeliveryGuard does not yet implement an outbox and cannot create
  atomicity across a transaction it does not own.
- **Evidence:** `TECHNIQUE_TAXONOMY.md`, D2 in `BENCHMARK_DESIGN.md`, and the
  Debezium outbox/delivery documentation.
- **Proposal-safe insight:** close the dual-write gap at the source transaction,
  then treat publication as retryable at-least-once work with stable identity
  and reconciliation.
- **Central index disposition:** add distinct card **Make the business write
  and delivery request atomic**.

## Scale delivery by proving claims, recovery, fairness and database health

- **Trigger:** several workers or destinations must drain HTTP work from a
  shared database.
- **Failure:** a queue can show good aggregate throughput while losing a claim
  after a crash, starving one destination, duplicating effects or accumulating
  dead tuples and index bloat.
- **Decision:** keep the local sender as control; prototype a maintained
  Python/Postgres queue before custom leases, then compare exact kill/reclaim,
  per-destination age and database growth. Try snapshot rotation only if the
  hot-row path actually fails.
- **Delivery control:** D1 reconciles every event/effect under 1/4/16 workers,
  skew, process kills and vacuum measurements.
- **Boundary:** D1 has not run; no scale or Procrastinate/PgQue claim is made.
- **Evidence:** D1 in `BENCHMARK_DESIGN.md` and
  `GITHUB_IMPLEMENTATION_AUDIT.md`.
- **Proposal-safe insight:** select a queue from its measured failure and
  operating region, not its “exactly once” label or headline throughput.
- **Central index disposition:** no new central card until D1 produces a local
  comparison; the note deepens the existing delivery-failure card.
