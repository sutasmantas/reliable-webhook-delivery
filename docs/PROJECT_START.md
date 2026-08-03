# DeliveryGuard project start

## 1. Restart boundary

- repository: `portfolio_demos/delivery_guard`
- baseline branch and commit: local `main` at pinned Tenacity commit
  `b3c5a9f9212187aaf96353378daa9a9ebd800742`
- implementation branch: `agent/delivery-guard-depth`
- assigned isolated worktree: `portfolio_demos/worktrees/delivery_guard_depth`
- owner/session: non-Context portfolio stream, 2026-08-01
- repositories/worktrees that are read-only: ContextSidecar and every portfolio
  repository other than an explicitly created integration worktree
- exact next action: implement the frozen delivery contract and its conformance
  tests; do not add a UI or decorative polish

Never share an active worktree or switch branches inside an assigned worktree.

## 2. Client outcome and non-duplication

- one client-purchased outcome this project proves: a reusable Python delivery
  boundary that prevents transient webhook failures, duplicate requests, and
  exhausted actions from becoming silent or untraceable
- existing portfolio evidence closest to it: Atlas durable ingestion jobs and
  Relay governed outbound actions
- mechanism or deliverable that is genuinely new: one installable contract
  with frozen conformance vectors, normalized outcomes, durable receipts, and
  deterministic replay semantics reusable across services
- why this is better coverage than deepening an existing project: the repeated
  reliability behavior becomes a tested delivery accelerator instead of a
  third app-local implementation

## 3. GitHub foundation comparison

Licensing was deliberately excluded from discovery and selection.

| Candidate | Repository | Activity/version checked | Central behavior reusable for this MRE | Adaptation cost/risk | Decision |
| --- | --- | --- | --- | --- | --- |
| Tenacity | `https://github.com/jd/tenacity` | `b3c5a9f`, current GitHub `main`, checked 2026-08-01 | bounded retry policies, exception predicates, per-call retry state, callbacks, injectable sleep | moderate: add domain outcomes and persistence without hiding the underlying retry engine | selected |
| Backoff | `https://github.com/litl/backoff` | `d82b23c`, current GitHub `master`, checked 2026-08-01; repository archived 2025-08-08 | sync/async retry decorators, give-up predicates, event callbacks | higher continuity risk because the repository is archived; callback dictionaries are less direct for typed attempt receipts | rejected |

Selected foundation:

- repository URL: `https://github.com/jd/tenacity.git`
- pinned tag/commit: `b3c5a9f9212187aaf96353378daa9a9ebd800742`
- exact code/package/contracts reused: `Retrying`, `stop_after_attempt`,
  `retry_if_exception`, wait policies, retry call state, and injectable sleep
- upstream history/identity preservation: cloned Git history is retained and
  the source remote is named `upstream`
- why this is faster/safer than starting blank: the retry loop, termination
  behavior, callback lifecycle, and sync/async primitives are already tested;
  portfolio work can focus on delivery semantics and evidence

## 4. Distinct visual direction

Not applicable in this slice. DeliveryGuard is an installable service kit and
CLI smoke demo, not a portfolio UI. No interface will be invented to make the
kit look more substantial. If a future client-facing UI is justified, it must
complete the full rendered comparison gate before implementation.

## 5. Minimum referenceable evidence contract

| Gate | Observable acceptance evidence | Status |
| --- | --- | --- |
| Central similarity | Tenacity `Retrying`, stop, wait, predicate, retry state, and injectable sleep power the executor | PASS |
| Working vertical slice | CLI registers, retries, persists receipts, deduplicates, dead-letters, and replays | PASS |
| No-key deterministic proof | scripted transport and CLI demo require no service credentials; committed output matches | PASS |
| Invalid input and abuse behavior | invalid keys, URLs, secret refs, payload collisions, and transitions refuse safely | PASS |
| Provider/tool failure and retry/refusal/handoff | frozen 2xx/409/429/4xx/5xx plus network/configuration/malformed/interruption tests | PASS |
| Focused mechanism tests | 18 DeliveryGuard tests; retained suite totals 190 passed, 1 skipped, 12 passed subtests | PASS |
| Clean-checkout quickstart | detached `1513cc3` standard-venv install, lint, type, tests, package, Twine, and demo | PASS |
| Cover-letter claim ledger | `docs/CLAIM_LEDGER.md` defines safe wording and defers standalone highlight status | PASS |
| Honest unsupported-claim boundary | no production-scale, exactly-once, distributed, endpoint-trust, or provider claim | PASS |

## 6. Verification and handback

- static/type/lint command: `.venv/Scripts/python -m ruff check deliveryguard tests/test_deliveryguard.py`; `.venv/Scripts/python -m ruff format --check deliveryguard tests/test_deliveryguard.py`; `.venv/Scripts/python -m mypy deliveryguard`
- focused tests: `.venv/Scripts/python -m pytest tests/test_deliveryguard.py -q` -> 18 passed; `.venv/Scripts/python -m pytest tests -q` -> 190 passed, 1 skipped, 12 passed subtests
- integration/demo command: `.venv/Scripts/deliveryguard demo --database .demo/delivery.sqlite3` -> PASS twice on one database; `docker run --rm deliveryguard:verify` -> PASS
- build/package command: `.venv/Scripts/python -m build`; `.venv/Scripts/python -m twine check dist/*` -> wheel and sdist PASS
- branch and final commits: `agent/delivery-guard-depth` at `b008f47f54b25596e0fafd2ecea921d59c5142cf`; merged local `main` at `fcd03777058c8201a78d108703e099820774b21a`
- clean state: detached verification at `1513cc3` returned no tracked changes; temporary worktree removed
- known boundaries: synchronous single-process SQLite; at-least-once attempts; no distributed leases, provider-specific policy, endpoint trust, UI, deployment, or standalone portfolio-highlight claim yet
- exact next portfolio action: build slice 4, the integration adapter conformance harness, as the first concrete DeliveryGuard consumer; do not add named adapters without repeated/live demand
