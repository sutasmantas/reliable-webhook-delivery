# DeliveryGuard publication evidence — 2026-08-03

## What the browser proves

`deliveryguard-viewer` runs the real credential-free `run_demo` lifecycle and
renders its SQLite-backed receipts. The evidence is generated at request time;
the page does not contain a hard-coded PASS response.

The deterministic lifecycle records:

- a 503 classified as retryable, followed by a successful second attempt;
- a repeated idempotency key that creates zero extra transport calls;
- a permanent 422 moved to dead letter without pointless retries;
- an explicit replay recorded as cycle 2 instead of overwriting cycle 1; and
- a configured secret value replaced with `[REDACTED]` in durable receipts.

## Verification results

| Gate | Command or artifact | Result |
| --- | --- | --- |
| Focused behavior | `.venv\\Scripts\\python -m pytest tests/test_deliveryguard.py -q --basetemp .pytest_focused` | 20 passed |
| Full regression | `.venv\\Scripts\\python -m pytest tests -q --basetemp .pytest_verify` | 192 passed, 1 skipped, 12 subtests passed |
| Strict typing | `.venv\\Scripts\\python -m mypy deliveryguard` | 12 source files, no issues |
| Changed-code lint | `python -m ruff check deliveryguard tests scripts` | PASS |
| Changed-code format | `python -m ruff format --check deliveryguard tests scripts` | PASS |
| Responsive browser | `python scripts/check_viewer_layout.py` | PASS at 1600×1200, 1024×900, and 390×844 |
| Package | `.venv\\Scripts\\python -m build --no-isolation` | wheel and sdist built |
| Distribution metadata | `.venv\\Scripts\\python -m twine check dist\\*` | both PASS |
| Packaged viewer | wheel archive inventory | `app.js`, `index.html`, and `styles.css` present |
| Container | `docker build -t deliveryguard:publication .` | PASS |
| Container lifecycle | `docker run --rm deliveryguard:publication` | JSON gate `PASS` |

The repository retains the vendored Tenacity foundation. The new lint gate is
intentionally scoped to DeliveryGuard-owned code, tests, and scripts; upstream
Tenacity source is not reformatted to satisfy a newer local Ruff release.

## Final media

| File | Format | SHA-256 |
| --- | --- | --- |
| `final_upload/01_cover.png` | 1600×1200 PNG | `7CF4E1E2A6CD6D3A1EFA244EDC90606F5D949DC3D88C8B21154C5F8321C19130` |
| `final_upload/02_workflow.png` | 1600×1200 PNG | `A64C6D58240ADE75E5E7DEB4220A0B4873F9F306975B4B2BC59763CA88861356` |
| `final_upload/03_proof.png` | 1600×1200 PNG | `4A7CDF54360964449310E7F31CBE2FA448E80CD00374E160C90CBC8DE68981A0` |
| `final_upload/04_deliveryguard_walkthrough.mp4` | 18.56 s, 1600×1200, H.264/yuv420p | `B8E589CAF3C1D0674A1688C9C4CA6B79A2719A3132AAF7A62EC80C15CDEF0B5D` |

The walkthrough has a stable opening frame, a visible synthetic pointer,
full-sentence captions, smooth scrolling, and a dedicated ending card.

## Claim boundary

This package demonstrates a local at-least-once delivery reference with a
stable idempotency contract. It does not prove distributed exactly-once
effects, multi-worker scale, provider-specific behavior, a production SLA, or
client impact. See [`CLAIM_LEDGER.md`](CLAIM_LEDGER.md).
