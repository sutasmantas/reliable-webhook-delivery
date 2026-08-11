# DeliveryGuard research decision

Date: 2026-08-05

## Outcome

The systematic evidence gate is `PASS`. Experiment and overall technique-ceiling gates remain `PARTIAL`: D0-D4 are frozen designs, not results.

The current SQLite/Tenacity sender remains the honest default for one bounded process. The first depth experiment is D0, followed by the maintained Procrastinate/Postgres claim profile in D1. There is no evidence-based reason to replace the current code with a broker or workflow runtime now.

## Retained decisions

| Decision | Disposition |
| --- | --- |
| stable event identity, explicit outcomes, receipts, DLQ/replay, redaction | invariant |
| deterministic fault/state reconciliation | D0 exact first experiment |
| Procrastinate/Postgres versus measured SQL control | D1 first scale/recovery comparison |
| PgQue snapshot rotation | only if D1 exposes sustained bloat/consumer-log need |
| transactional outbox | required when delivery derives from a source-owned business transaction |
| Debezium CDC | conditional on freshness or an existing Kafka/Debezium estate |
| full jitter, bounded `Retry-After`, per-destination backpressure | D3 |
| Standard Webhooks-compatible raw-body verification | D3 receiver profile |
| Temporal/DBOS/Restate | deferred until a multi-step long-running workflow exists |
| Celery/Svix wholesale adoption | rejected for current bounded scope |

## Exact next controlled work

1. D0 common fault manifest, deterministic clock/RNG and reconciliation oracle.
2. D1 current control versus Procrastinate/Postgres under concurrency and kill boundaries; write only thin adapters after copying/refitting maintained component behavior.
3. D2 only with a source-owned transaction fixture.
4. D3 only after the claim/recovery result is stable.
5. D4 only if a real multi-step requirement crosses the admission gate.

No experiment, implementation, visual polish, merge, push or publication was performed in this slice.

## Eleven systematic evidence gates

| Gate | Status | Evidence |
| --- | --- | --- |
| Problem decomposition | PASS | transaction through observability layers in `TECHNIQUE_TAXONOMY.md` |
| Search protocol | PASS | dated sources and eight reproducible iterations |
| Survey coverage | PASS | standards, primary guidance and maintained family implementations |
| Benchmark coverage | PASS | exact local vectors plus D0-D4 fault/load designs |
| Existing-answer search | PASS | closed architecture/protocol questions separated from local winners |
| Technique-family saturation | PASS | iterations 6 and 7 added no top-level family |
| Candidate comparison | PASS | `EVIDENCE_MATRIX.csv` |
| Contrary evidence | PASS | at-least-once, bloat, fairness, service-cost and guarantee limits |
| Implementation evidence | PASS | exact pins and reuse seams in `GITHUB_IMPLEMENTATION_AUDIT.md` |
| Portfolio fit | PASS | strengthens integration reliability without duplicating Relay/AdapterProof |
| Review status | PASS | conclusions explicitly labelled |

## Claim boundary

Defensible now: DeliveryGuard proves its bounded local lifecycle and supplies a systematic, pinned plan for atomicity, multi-worker claims, backpressure, signatures and durable workflow admission.

Not defensible now: distributed or production scale, source-write atomicity, fair scheduling, cryptographic authenticity, receiver processing, broker/workflow integration, or exactly-once delivery/effect.

