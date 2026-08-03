# DeliveryGuard publication slice

Date: 2026-08-03

## Acceptance contract

This slice presents the existing delivery lifecycle; it does not invent another
queue or reliability engine. It passes when the browser runs the real
credential-free demo and visibly proves transient recovery, duplicate
suppression, permanent-failure dead letter, explicit replay, append-only
receipts, and secret redaction. Every displayed count and receipt must come from
the generated demo response.

The final package requires three 1600×1200 images and one 15–22 second video,
responsive browser checks, canonical Upwork copy, a clean quickstart, and a
user-owned public repository. It must not claim exactly-once effects,
distributed workers, a hosted monitoring service, throughput, SLA, or a client
incident reduction.

## Reuse decision

The technical GitHub/component audit remains closed. The publication layer uses
the existing `run_demo`, SQLite receipts, package tests, and standard-library
HTTP serving pattern already proven by AdapterProof. React, FastAPI, and a
separate dashboard framework were rejected because this surface needs one
generated JSON endpoint and a bounded evidence renderer; they would add more
build and upgrade work than responsibility removed.

## Distinct visual identity

DeliveryGuard uses an incident flight-recorder metaphor: a warm technical
canvas, one horizontal attempt trace, a selected receipt, and a large recovery
control. It avoids AdapterProof's dark protocol lab/case matrix and
PipelineForge's reconciliation table. Orange marks retry/attention, green marks
delivered recovery, and blue marks terminal classification.
