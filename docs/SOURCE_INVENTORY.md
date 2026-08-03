# DeliveryGuard source inventory

This inventory freezes the reusable behavior before extraction. It is based on
working project commits, not planned features. ContextSidecar is deliberately
excluded because it is owned by another agent.

| Contract | Atlas `e8d9cf5` | Relay `7d4711e` | Website Assistant `9f2064a` | Extraction decision |
| --- | --- | --- | --- | --- |
| scoped idempotency | `app/jobs.py`: unique, tenant/principal-scoped keys return the existing job | `support_desk/outbound.py`: stable action key sent in a configurable header | `app/lib/handoff.ts`: SHA-256 request key sent as `Idempotency-Key` | include canonical keys and duplicate terminal receipt lookup; exclude tenant ACL policy |
| normalized outcome | job states distinguish retryable failure and dead letter | 409 is already applied; 429/5xx/timeout retry; other 4xx stop | 409 is already accepted; 429/5xx/network retry; other failures reject | freeze a small transport-independent taxonomy |
| bounded retry | job `attempts` and `max_attempts` bound retries | retryable and terminal exceptions drive action attempts | failure class is exposed to caller but retry scheduling is app-local | include policy and receipts; do not extract full app job orchestration |
| durable recovery | SQLite failed/dead-letter states and explicit replay | SQLite action attempts, dead-letter, receipts, and replay | no durable outbox | include SQLite action/attempt store from two proven apps |
| correlation | validated request IDs flow through structured logs | ticket/action IDs and persisted events correlate execution | stable handoff key correlates delivery | include validated/generated correlation IDs in every receipt; exclude Atlas tenant/principal logging |
| safe evidence | error messages and structured state avoid raw provider bodies | configured recursive redaction and secret references | returned errors omit endpoint responses | include env secret references and recursive evidence redaction |

## Frozen minimum contract

DeliveryGuard will provide only:

1. canonical idempotency and correlation identifiers;
2. HTTP/network outcome normalization;
3. bounded retry driven by Tenacity;
4. durable action state plus append-only attempt receipts;
5. dead-letter and explicit replay;
6. environment secret references and recursive redaction;
7. deterministic conformance vectors, CLI smoke proof, packaging, and CI.

Excluded from this slice: tenant authorization, SSRF enforcement, distributed
leases, async workers, provider/model configuration, token/cost accounting,
circuit breakers, dashboards, and a UI. Those are not uniformly proven across
the source projects or are application-specific controls.

