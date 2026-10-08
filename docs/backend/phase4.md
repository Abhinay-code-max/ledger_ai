# Phase 4 accounting assurance operations

Phase 4 completes Role 4's accounting control plane. Role 2 remains authoritative for journal
validation and posting, period validation and close, and financial statement calculation. Role 4
persists the operation state, immutable confirmation or snapshot, audit chain, provenance graph, and
progress projection.

## Delivery surface

- Generated v1 JSON Schemas and synthetic fixtures cover validation, posting, status, close,
  statements, provenance, and progress contracts.
- Migration `20261008_04` creates ten tenant-scoped tables with forced RLS. Confirmation, statement,
  audit, provenance, and progress-history tables grant runtime only `SELECT, INSERT` and also have
  mutation-rejection triggers. Accounting periods have a database exclusion constraint preventing
  overlaps per tenant and legal entity.
- `POST /api/v1/posting-operations` validates that the exact proposal version has an approved review,
  belongs to an open period, and has a posting date inside the period. A tenant-scoped advisory lock
  makes idempotency-key resolution race safe.
- `POST /api/v1/posting-operations/{operation_id}/recover` looks up an `UNKNOWN` or `IN_PROGRESS`
  operation by its original ID. It never repeats the posting mutation.
- Accounting-period create/list and close/recover endpoints coordinate Role 2 validation and close.
  A period is marked `CLOSED` only from a bound Role 2 confirmation.
- Statement capture stores the exact available Role 2 snapshot and exact-decimal lines as immutable
  evidence. Role 4 performs no statement arithmetic.
- Audit events form a serialized SHA-256 hash chain per tenant. Provenance traces traverse stored
  edges in both directions with a hard node bound.
- Every state transition appends a progress event and updates the current projection. Authenticated
  `GET /api/v1/progress-stream` uses SSE, accepts `Last-Event-ID`, replays in deterministic
  `(occurred_at, id)` order, rejects unknown tenant-scoped cursors, and sends idle heartbeats.

## Permissions

`posting:execute` protects posting and recovery, `period-close:request` protects period creation and
close, `financial-statement:read` protects period and statement reads, `audit:read` protects audit and
provenance, and `progress:read` protects projections and SSE. All endpoints still require the normal
JWT, workspace, organization, and legal-entity context.

## Failure and recovery

Role 2 timeouts and HTTP 408/504 responses become `UNKNOWN`. Operators or workers call the recovery
endpoint until Role 2 returns a terminal bound result. Contract, tenant, operation, proposal, period,
or version mismatches are rejected as untrusted downstream responses. Non-ambiguous terminal adapter
errors become `FAILED`; rejected accounting evidence becomes `REJECTED` or `BLOCKED`.

Deploy by running `alembic upgrade head`, then the idempotent seed to publish the new permissions.
Role 2 must implement the fixed v1 adapter paths and retain idempotency/status records. Verification is
the frozen dependency install, migration upgrade/downgrade/upgrade cycle, formatting, lint, strict
typing, dependency audit, license summary, generated-artifact checks, OpenAPI check, full tests, and
compile-all sequence used by CI.
