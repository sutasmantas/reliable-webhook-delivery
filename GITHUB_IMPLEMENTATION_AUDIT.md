# DeliveryGuard GitHub implementation audit

Date: 2026-08-05

Purpose: reuse maintained queue, workflow, protocol and fault components before writing consequential delivery logic. Licenses are intentionally ignored by portfolio policy; fit, maintenance, defects and glue cost determine adoption.

## Current seams

- `executor.py` owns one delivery attempt and retry orchestration.
- `classification.py` owns normalized HTTP/network outcomes.
- `store.py` owns durable attempts, receipts, idempotency and replay state.
- `adapter.py` owns the outbound HTTP boundary.

Keep classification and evidence contracts stable. Replace or extend the store, claim/scheduler and protocol adapters only behind those seams.

## Repository comparison

| Repository and inspected pin | Health on 2026-08-05 | Reusable component | Important boundary | Decision |
| --- | --- | --- | --- | --- |
| [jd/tenacity](https://github.com/jd/tenacity) `b3c5a9f` | active 2026-08-01; 47 open issues | retry composition already used | no durable schedule, rate fairness or queue claim | retain; inject clock/RNG and add bounded jitter/Retry-After policy |
| [procrastinate-org/procrastinate](https://github.com/procrastinate-org/procrastinate) `d9cf91d` | active 2026-07-31; 91 open issues | Python/Postgres jobs, locks, retries and worker lifecycle | integration and schema/claim semantics must be tested under kill/reclaim | preferred component prototype for multi-worker Postgres; do not reimplement a queue first |
| [timgit/pg-boss](https://github.com/timgit/pg-boss) `55ee32f` | active 2026-08-03; 27 open issues | mature Postgres queue reference | Node runtime; job delivery is not external-effect exactly once | comparative evidence, not a Python dependency |
| [NikolayS/PgQue](https://github.com/NikolayS/PgQue) `95d5c3c` | active 2026-07-26; v0.1; 84 open issues | snapshot/table-rotation SQL queue | young design and seconds-scale default latency | benchmark only if hot-row/vacuum pressure appears |
| [celery/celery](https://github.com/celery/celery) `571efe8` | active 2026-08-04; 799 open issues | distributed broker workers/routing | broker operations and broad configuration surface | defer until an explicit distributed throughput/isolation requirement |
| [debezium/debezium](https://github.com/debezium/debezium) `1397c91` | active 2026-08-04; 118 open issues | outbox event router and CDC | at-least-once duplicates; Kafka/Connect or engine boundary | reuse only where source transaction and existing CDC platform justify it |
| [temporalio/sdk-python](https://github.com/temporalio/sdk-python) `39b820d` | active 2026-08-04; 110 open issues | durable workflow/timers/replay/time-skipping tests | separate service/worker and deterministic workflow constraints | conditional long-running multi-step prototype |
| [dbos-inc/dbos-transact-py](https://github.com/dbos-inc/dbos-transact-py) `4ed0d55` | active 2026-08-05; 7 open issues | embedded Postgres durable workflows/queues | framework semantics and external effects still require idempotency | lighter conditional Python prototype than a custom workflow engine |
| [restatedev/sdk-python](https://github.com/restatedev/sdk-python) `5dfca1a` | active 2026-07-24; 20 open issues | durable handlers, calls and webhook dedupe | requires Restate runtime; guarantee scope must remain explicit | record as alternative, not first experiment |
| [Shopify/toxiproxy](https://github.com/Shopify/toxiproxy) `94d6d4b` | active 2026-08-04; 104 open issues | network latency/timeout/reset/bandwidth faults | no DB/process/business-semantic faults | adopt in shared experiment harness |
| [standard-webhooks/standard-webhooks](https://github.com/standard-webhooks/standard-webhooks) `2919676` | active 2026-08-05; 56 open issues | signature formats and libraries | receiver-side protocol; key management remains local | refit a thin verification profile; do not invent signature conventions |
| [cloudevents/spec](https://github.com/cloudevents/spec) `c2845a4` | active 2026-07-23; 15 open issues | portable event envelope | not security, queueing or dedupe | defer until interoperability need |
| [svix/svix-webhooks](https://github.com/svix/svix-webhooks) `ff6af43` | active 2026-08-04; 58 open issues | complete webhook service/reference | replaces rather than extends bounded component | reference algorithms/protocols; never copy service wholesale |

## Reuse map before custom logic

| Need | First source to reuse | Project-owned adapter/check |
| --- | --- | --- |
| Postgres workers | Procrastinate | map DeliveryGuard event/outcome/receipt contract; kill/reclaim/fairness test |
| source atomicity | source-owned outbox + Debezium pattern | event identity, payload/version and reconciliation report |
| retry policy | Tenacity + RFC/AWS rules | injected clock/RNG, bounds and exact conformance vectors |
| network faults | Toxiproxy | scripted scenario manifest and state reconciliation |
| signatures | Standard Webhooks library/spec | raw-body/key provider, replay window and redacted evidence |
| long workflow | Temporal or DBOS | activity adapter retaining current idempotency/outcome contract |
| common event envelope | CloudEvents SDK/spec | domain payload and authorization remain application-owned |

## Explicit non-adoptions

- Do not hand-write a distributed queue, lease protocol or durable workflow engine before the maintained candidates fail the exact local experiment.
- Do not call a queue acknowledgement, sender receipt, Kafka EOS setting or workflow completion an exactly-once external business effect.
- Do not add Celery, Temporal, DBOS and Restate together. One operating-region requirement selects at most one prototype.
- Do not bolt an outbox onto a different database transaction and claim atomicity; the outbox row must share the source transaction.
- Do not parse JSON before signature verification when the protocol signs raw bytes.

## Minimal integration checks

1. Preserve current exact outcome, receipt, redaction, dedupe/collision and DLQ conformance cases.
2. Kill a worker after claim, after HTTP effect and before receipt; prove lease recovery and reconcile every state/effect.
3. Run at least two workers and two destinations; report duplicate effects, starvation, queue age, throughput, p95 latency and database bloat.
4. Bound `Retry-After`, backoff and jitter with a deterministic clock/RNG.
5. Verify signatures on raw bytes across current/previous key, stale timestamp, changed body and replay cases.
6. Disable optional Postgres/workflow/signature profiles and retain the current single-process control.

