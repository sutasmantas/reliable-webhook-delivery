# DeliveryGuard technique taxonomy

Date: 2026-08-05

Status: systematic research dossier; no implementation or experiment is authorized in this slice. Conclusions use `established`, `provisional`, `contested`, or `unknown`.

## Decision boundary

DeliveryGuard currently proves a bounded, synchronous, single-process HTTP delivery lifecycle backed by SQLite: stable idempotency keys, normalized outcomes, Tenacity retries, redacted receipts, dead letter and explicit replay. It does not prove atomic creation with a business write, multi-worker claiming, distributed durability, receiver processing, ordering, fairness, production throughput, or exactly-once delivery.

The paid outcome is recoverable external delivery with an auditable truth boundary. The technique decision must therefore separate transaction capture, work claiming, retry scheduling, HTTP protocol/security, receiver idempotency, and recovery evidence instead of treating “use a queue” as one choice.

## Problem decomposition

| Layer | Independent decision | Serious families | Current boundary |
| --- | --- | --- | --- |
| business atomicity | avoid committed business state without queued delivery | direct send; dual write; transactional outbox; change-data capture | caller enqueues separately |
| durable work store | retain pending work through process failure | SQLite/Postgres table; snapshot/rotating Postgres queue; Redis/broker; durable workflow runtime | SQLite |
| claiming | prevent concurrent workers owning the same attempt | process mutex; row lock/`SKIP LOCKED`; lease/heartbeat; broker visibility timeout; workflow task | one process |
| scheduling | decide when and how work retries | fixed delay; exponential; bounded exponential with jitter; server `Retry-After`; circuit/rate policy | fixed Tenacity wait |
| delivery semantics | define observable success/failure | at-most-once; at-least-once; sender acknowledgement; receiver dedupe/effectively-once | at-least-once attempts plus local receipt |
| ordering/fairness | prevent one endpoint/tenant or poison item dominating | FIFO; per-key ordering; round robin; per-destination concurrency/rate limit; priority/aging | not measured |
| HTTP classification | map transport/status/body outcomes | RFC status/retry hints; provider rules; application acknowledgement | frozen bounded mapping |
| authenticity/replay | prove origin and bound replay | HMAC/Ed25519 raw-body signatures; HTTP message signatures; timestamp/tolerance; key rotation | none |
| envelope | carry stable event identity and metadata | application JSON; CloudEvents; provider-specific webhook | application JSON |
| recovery | reclaim interrupted work and reconcile truth | lease expiry; visibility timeout; workflow replay; outbox reconciliation; manual DLQ replay | interrupted-attempt recovery and manual replay |
| fault evaluation | reproduce partial failures | scripted fake; Toxiproxy; process kill; clock/rate faults; model/state reconciliation | scripted local fake |
| observability | explain attempts without leaking secrets | receipts/metrics/traces; queue lag; age/fairness; redaction | redacted receipts |

## Technique families and operating regions

### Local durable sender — `established local control`

SQLite plus Tenacity is appropriate for one process and bounded volume. It is transparent and already contract-tested. It cannot safely infer multi-worker ownership or atomicity with an independent business database.

### PostgreSQL row-claim queues — `established family`, `unknown local winner`

`FOR UPDATE ... SKIP LOCKED` is documented as suitable for queue-like access, although it intentionally presents an inconsistent view. A lease/expiry is needed when work outlives the claiming transaction. Procrastinate and pg-boss are maintained implementations; the former matches Python/Postgres while the latter is comparative Node evidence. Fairness, hot-row churn, vacuum pressure and recovery must be measured rather than assumed.

### Snapshot/rotating PostgreSQL queues — `provisional specialized profile`

PgQue replaces hot update/delete claiming with snapshot batches and table rotation. It explicitly trades single-digit-millisecond dispatch for sustained queue stability and multi-consumer event-log behavior. It is a distinct candidate when Postgres bloat dominates, not the first fit for this small HTTP sender.

### Broker-backed queues — `established family`, `conditional`

Celery-class brokers provide distributed workers, visibility/redelivery, routing and operational tooling. They add a broker and worker control plane and do not make external HTTP effects exactly once. Adopt only when throughput, isolation or existing infrastructure justifies that boundary.

### Transactional outbox — `established invariant when source write matters`

Writing business state and an outbox row in one transaction closes the dual-write gap. A poller or Debezium outbox event router can publish afterward; Debezium documents stable event IDs and partition keys and remains at-least-once by default. This pattern cannot be retrofitted solely inside DeliveryGuard when the source transaction is owned elsewhere.

### Durable execution runtimes — `established family`, `conditional`

Temporal, DBOS and Restate persist workflow progress, timers and retries. Temporal is a separate service/worker architecture; DBOS is an embedded Postgres-backed Python option; Restate exposes durable handlers and webhook deduplication. These are justified by multi-step, long-running workflows—not a single bounded POST. Vendor “exactly once” language must not be extended to an uncooperative external endpoint.

### Retry, rate and backpressure policy — `established principles`

Bounded exponential backoff with jitter reduces synchronized retry storms; RFC 9110 defines `Retry-After` as a date or delay. Per-destination concurrency and rate limits prevent a noisy endpoint consuming global capacity. The exact policy remains workload/provider-specific and needs a deterministic clock.

### Receiver idempotency/effectively-once effects — `established boundary`

Retries necessarily allow duplicate attempts. A stable event/idempotency key and receiver-side durable deduplication can make a particular business effect effectively once. Sender receipts alone cannot establish receiver durability or processing completion.

### Webhook signatures and replay controls — `established protocol family`

Standard Webhooks and mature provider guidance converge on verifying the raw body, timestamp/replay window and signature before parsing. Key rotation and constant-time comparison are required. RFC 9421 is a broader HTTP Message Signatures option; use protocol-specific conventions where interoperability requires them.

### CloudEvents envelope — `established interoperability option`

CloudEvents standardizes source/id/type/time/content metadata and defines duplicate identity through source plus id. It does not supply transport security, queueing or receiver idempotency. Adopt only when multiple producers or consumers need a shared envelope.

### Fault injection and reconciliation — `established evaluation need`

Scripted fakes remain the exact classification oracle. Toxiproxy adds latency, timeouts, resets and bandwidth faults; process kills and database faults cover claim recovery. Every run must reconcile events, attempts, acknowledgements, DLQ rows and observed receiver effects rather than report request counts alone.

## Search protocol

- Search date: 2026-08-05.
- Sources: PostgreSQL, IETF/RFC, AWS, Stripe, Debezium, Temporal/DBOS/Restate, Standard Webhooks and CloudEvents documentation; primary papers; maintained GitHub repositories and current issue/release metadata.
- Main window: 2024-2026, retaining older standards and algorithms when still authoritative.
- Excluded: vendor rankings, popularity-only choices, unsupported exactly-once claims, and all license research/ranking.

| Iteration | Query family | New decision-relevant family |
| ---: | --- | --- |
| 0 | durable HTTP/webhook retry, outbox, idempotency | outbox, receiver dedupe, retry policy |
| 1 | Postgres queue algorithms and multi-worker claiming | row claim/lease and broker regions |
| 2 | durable execution Python implementations | Temporal and DBOS |
| 3 | webhook signatures, CloudEvents, fault injection | protocol security, envelope, Toxiproxy |
| 4 | 2026 Postgres queue developments | PgQue snapshot/rotation |
| 5 | durable webhook alternatives and emerging semantics | Restate; IETF delivery draft retained only as provisional vocabulary |
| 6 | per-destination fairness, rate limiting, advisory locks | no family; refined fairness and lock limitations |
| 7 | broker/workflow backpressure and delivery controls | no family; confirmed conditional broker/durable-runtime region |

Iterations 6 and 7 added no top-level family after Restate and PgQue were included. Saturation is `PASS` for the dated scope.

## Primary anchors

- [PostgreSQL `SELECT` / `SKIP LOCKED`](https://www.postgresql.org/docs/current/sql-select.html)
- [Debezium outbox event router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [Debezium delivery semantics](https://debezium.io/documentation/reference/3.5/configuration/eos.html)
- [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110)
- [AWS retry behavior](https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html)
- [Standard Webhooks](https://github.com/standard-webhooks/standard-webhooks)
- [CloudEvents](https://github.com/cloudevents/spec)
- [Temporal Python SDK](https://github.com/temporalio/sdk-python)
- [DBOS Python](https://github.com/dbos-inc/dbos-transact-py)
- [Restate durable webhooks](https://docs.restate.dev/guides/durable-webhooks)
- [PgQue](https://www.postgresql.org/about/news/pgque-v01-zero-bloat-postgres-queue-3284/)
- [Toxiproxy](https://github.com/Shopify/toxiproxy)

