# DeliveryGuard benchmark design

Date: 2026-08-05

Status: design only. No Postgres, broker, workflow runtime, proxy or experiment was executed in this slice.

## Questions closed by external evidence

| Question | Closed decision |
| --- | --- |
| Can sender receipts prove exactly-once receiver processing? | no; retries duplicate attempts and receiver durability is outside the sender boundary |
| Can business state and delivery be made atomic by two independent writes? | no; use a shared transactional outbox or an application-level reconciliation boundary |
| Should every retry use a fixed delay? | no; bound exponential backoff/jitter and honor bounded server hints where applicable |
| Is one queue/runtime universally best? | no; local, Postgres, broker and durable-workflow regions have different operating costs |
| Should DeliveryGuard implement a distributed queue from scratch first? | no; prototype maintained components behind the existing lifecycle contract |

## Common evidence contract

Each case records immutable event ID/idempotency key/payload digest, source transaction marker when present, destination/tenant, enqueue/claim/lease times, worker and attempt IDs, exact request digest, response/exception class, retry-decision inputs, receipt/DLQ/replay transition, observed receiver effect and final reconciliation result. Secrets and signed payload material remain redacted. A fake monotonic/wall clock and seeded RNG make scheduling exact.

### Frozen workload

- 10,000 events across 20 destinations and four tenants; skew profiles 1:1 and 80:20; stable payload sizes 1 KB/64 KB/1 MB.
- Faults: 200/202/204, 409, 408, 425, 429 with seconds/date/malformed `Retry-After`, 500/503, malformed response, connect/read timeout, reset, process kill at every lifecycle boundary, database restart and clock skew.
- Receiver modes: idempotent durable dedupe, non-idempotent counter, delayed acknowledgement, acknowledgement-before-processing and signature verifier.
- Every run ends with exact reconciliation of source rows, queue rows, attempts, receipts, DLQ entries and receiver effects.

## D0 — harness and state-model reconciliation (exact first experiment)

Adapt the existing fake-server vectors to one scenario manifest, add Toxiproxy network faults, deterministic time/RNG and a reference state transition model. Mutation checks delete an attempt, duplicate an effect, corrupt a digest and strand a claim; the scorer must detect all four. PASS requires zero unexplained rows/effects, stable replay from a frozen seed and the current test suite unchanged.

Budget: CPU/local containers, four hours, no external endpoints.

## D1 — multi-worker Postgres claim/recovery

Compare current SQLite single worker, a minimal measured SQL control and a Procrastinate-backed implementation. Use 1/4/16 workers, balanced/skewed destinations, short/long processing and kills after claim/effect/before receipt. Measure throughput, p50/p95/p99 latency, oldest queue age, redeliveries, duplicate receiver effects, starvation, reclaim time, dead tuples/table/index size and CPU/IO.

Promotion requires zero lost events, zero duplicate effects with the idempotent receiver, complete reconciliation, no destination starved beyond twice the declared scheduling window, and at least 2x throughput at four workers without more than 25% database-size drift after vacuum. If hot-row churn is material, compare PgQue snapshot rotation as a specialist follow-up; otherwise stop.

## D2 — source atomicity and outbox publication

On one Postgres transaction, compare unsafe business-write/direct-enqueue, transactional outbox with polling, and Debezium only if an existing CDC runtime is realistic. Crash before/after commit, between poll/publish/mark and during restart. PASS requires no committed business row without a discoverable outbox event, no published event without committed business state, stable identity across duplicates and complete eventual reconciliation. CDC is promoted only for a material freshness or existing-platform advantage.

## D3 — retry, backpressure and signature profile

Compare fixed delay, exponential, full jitter and bounded `Retry-After` under simultaneous 429/503 recovery. Add global versus per-destination concurrency and rate limits. Report recovery throughput, retry burst peak, healthy-destination p95 latency and starvation. Verify Standard Webhooks-compatible signatures on raw bytes across key rotation, stale timestamps, altered bodies and replays.

Hard gates: no retry beyond configured attempt/elapsed budgets; malformed or huge hints are bounded; one failing destination cannot consume all workers; invalid/stale/replayed signed requests produce no business effect.

## D4 — durable workflow admission (conditional)

Run only if a representative job has multiple externally visible steps, timers longer than a process lifetime, cancellation/signals or compensation. Compare the retained Postgres queue with one of Temporal or DBOS—not both at first—using the same state/effect reconciliation. Promote only for a unique recovery/operability win that pays for service/framework complexity. Restate is an alternate implementation, not an automatic third arm.

## Confounders and stopping rules

- Keep receiver behavior, HTTP client, payload, database hardware and fault schedule fixed across queue profiles.
- Separate attempt duplication from business-effect duplication.
- Run warm-up, five measured repetitions and confidence intervals for timing; exact state gates apply to every repetition.
- Do not use aggregate throughput to hide destination starvation or database growth.
- Stop at D1 if the bounded local sender meets the declared workload. Stop at D3 if maintained components satisfy the lifecycle; custom queue/workflow logic is not a portfolio objective.

