# DeliveryGuard claim ledger

## Supported now

| Claim | Evidence | Boundary |
| --- | --- | --- |
| Built a reusable Python delivery contract for idempotent webhook/tool actions | `deliveryguard/`, package build, Docker smoke | reusable kit, not a hosted service |
| Normalized 2xx, 409, 429, 4xx, 5xx, network, malformed-response, configuration, and interrupted-worker outcomes | frozen `tests/fixtures/delivery_conformance.json` plus adapter/store tests | generic HTTP semantics, not provider-specific behavior |
| Used bounded retries for transient outcomes and stopped immediately on permanent failures | `DeliveryExecutor`, Tenacity controller, transient/exhaustion/terminal tests | at-least-once attempts; destination must honor the idempotency key |
| Persisted redacted action and attempt receipts with dead-letter and explicit replay | SQLite store, replay and recovery tests, deterministic demo | single-process SQLite implementation, not a distributed queue |
| Kept secrets behind environment references and out of durable evidence | adapter/secret/redaction tests and demo database inspection | field-name redaction is a configured safety layer, not a DLP system |
| Shipped reproducible package, CI, and container smoke paths | wheel/sdist + Twine checks, workflow, Docker PASS | no deployment or uptime claim |
| Packaged the contract for typed reuse and exercised it in a concrete integration harness | `py.typed`, AdapterProof `6dd45c0` using the vendored wheel from `850cfd`, strict mypy, and 20 passing wire cases | reference through the AdapterProof integration outcome; not a hosted product |

## Proposal-safe wording

> I built a reusable delivery boundary that classifies webhook failures before
> retrying, uses stable idempotency keys, records each attempt, and moves
> exhausted or permanent failures to an explicit replay path.

AdapterProof is now the first concrete consumer. Reference DeliveryGuard as the
tested reliability mechanism inside that integration outcome. Use DeliveryGuard
directly for webhook reliability, retry, idempotency, and replay jobs; use
AdapterProof when the job is primarily about external API conformance.

## Unsupported wording

Do not claim:

- exactly-once delivery or prevention of duplicate side effects without a
  cooperating destination;
- distributed leases, multi-worker concurrency, production scale, or measured
  throughput;
- a deployed/hosted reliability platform, monitoring dashboard, or SLA;
- support for Salesforce, HubSpot, Slack, Twilio, or another named provider;
- endpoint trust or SSRF protection from this kit;
- client outcomes, revenue gains, reduced incidents, or live production use.
