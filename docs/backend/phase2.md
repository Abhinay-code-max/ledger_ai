# Phase 2 secure ingestion and asynchronous workflow foundation

## Scope and trust boundaries

Phase 2 accepts immutable PDF, JPEG, PNG, and bounded bank CSV evidence. Filenames, multipart
fields, object metadata, CSV cells, events, and future model output are hostile. Phase 1 verified
membership supplies tenant, organization, and legal-entity scope; bodies cannot override it.

This phase does not implement extraction, reconciliation, accounting, policy, approval, period
close, statements, or production Role 1/2/3/6 integrations. Typed deterministic doubles document
those future boundaries without pretending the services exist.

## Local startup

```shell
cp .env.example .env
uv sync --all-extras --frozen
docker compose up -d postgres redis minio minio-init
uv run alembic upgrade head
uv run ledgerai-seed
uv run uvicorn ledgerai_backend.main:app
```

MinIO is built from verified upstream source tags because its historical binary endpoint no longer
serves this release. The local bucket is private, versioned, and automatically encrypted with a
synthetic development key. Replace every local credential through deployment secret management.

The idempotent NOVA seed grants Phase 2 document capabilities through the existing Phase 1 roles.
It deliberately creates no evidence objects, imports, or processing jobs: those records require
real object-store provenance and must enter through the ingestion APIs.

## Upload sequence and scanning

1. `POST /api/v1/documents/uploads` validates a bounded request and durable idempotency key.
2. The server creates document/version rows and an opaque quarantine key.
3. The client receives a short-lived PUT-only presigned URL.
4. Completion rereads the object and verifies size, SHA-256, declared type, and magic bytes.
5. The scanner records identity, version, signature version, result, time, hash, and safe code.
6. Only `CLEAN` becomes `ACCEPTED`; suspicious/infected is `REJECTED`; unavailable/error/timeout
   remains `QUARANTINED`.
7. Acceptance and `document.uploaded.v1` outbox creation commit atomically.

Supported types are `application/pdf`, `image/jpeg`, and `image/png`; the default upload maximum is
10 MiB and the presign lifetime is five minutes. There is intentionally no evidence download API.

## CSV normalization

CSV is UTF-8 or UTF-8 BOM with required `booking_date`, `amount`, `currency`, and `direction`
columns. Dates accept ISO `YYYY-MM-DD` or `DD/MM/YYYY`. Amounts must be unsigned, canonical decimal
strings—no floats, signs, exponent notation, or zero—and direction is `DEBIT` or `CREDIT`.
Currencies normalize to three uppercase letters. NUL bytes, duplicate/missing headers, excess rows
or columns, oversized cells, malformed quoting, formula prefixes, and invalid encodings fail safely.

Valid rows become Phase 0 `BankTransaction` objects before persistence. Invalid rows receive a row
number, safe code, and safe message; narrations and entire rows are never logged. Fingerprints omit
row order, so reordered imports still deduplicate by bank account and normalized content.

Transaction lists use UUID-ascending keyset pagination (`after`) with the UUID as the unique,
deterministic tie-breaker. A known import may be supplied as `import_id`; it is verified in the
caller’s tenant/entity scope before its rows are listed, and foreign imports have the same neutral
not-found behavior as other scoped resources. A newly imported row is therefore retrieved through
its import filter, not assumed to occupy the first page of an unfiltered collection.

## Idempotency

Records are uniquely scoped by tenant, actor, operation, and key. They store only a canonical
SHA-256 request fingerprint, safe resource reference, status, correlation ID, and expiry. Same key
and same fingerprint returns the effective resource; different content returns `409`. The default
retention is 24 hours. Expired-row cleanup is an operational scheduled task; it must delete only
expired terminal records in bounded batches.

## Jobs, outbox, inbox, and recovery

Jobs implement `QUEUED`, `PROCESSING`, `RETRY_SCHEDULED`, `REVIEW_REQUIRED`, `COMPLETED`, `FAILED`,
and `DEAD_LETTERED`. Legal transitions and optimistic versions are enforced by the service and
attempt bounds by PostgreSQL. Retry requires `document:write`, an `If-Match` version, a retryable
failed state, and remaining attempts.

Outbox dispatch uses `FOR UPDATE SKIP LOCKED`. Publication failure increments attempts and schedules
bounded exponential backoff. Redis outage never rolls back committed API state; restart the
dispatcher after Redis recovers. Inbox claims use unique `consumer_name + event_id`, so duplicate
broker delivery is harmless. Dead-letter inspection must use tenant-scoped operational queries;
repair the cause and replay by creating an authorized new attempt, never by erasing history.

The relay can also be given one known event ID for tenant-scoped operational recovery. That filter
is applied before the row is locked, so a busy bounded batch cannot hide the selected event. It
does not bypass RLS, due-time checks, or normal attempt/dead-letter accounting.

Correlation IDs flow through database rows, event references, queue arguments, and inbox records.
Metrics use only operation/outcome/state labels—never filenames, object keys, URLs, narrations,
tokens, tenant IDs, or DSNs.

## Database and RLS

Migration `20261006_02` adds `documents`, `document_versions`, `document_scan_results`,
`transaction_imports`, `bank_transactions`, `transaction_import_errors`, `processing_jobs`,
`job_attempts`, `outbox_events`, `consumer_inbox`, and `idempotency_records`. All eleven carry full
tenant/entity scope, composite foreign keys, forced RLS with `USING` and `WITH CHECK`, and direct
least-privilege grants to the non-owner runtime role.

## Verification and recovery

```shell
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run python tools/generate_contract_artifacts.py --check
uv run python tools/generate_openapi.py --check
uv run pytest
uv run python -m compileall -q src tools tests
```

For migration failure, retain the error, never stamp past it, and retry on a restored copy. Verify
both empty upgrade and `20261006_01 -> 20261006_02`, repeated upgrade, downgrade/re-upgrade, and one
head. For Redis failure, leave outbox rows pending. For MinIO failure, keep uploads non-accepted and
retry completion with the same idempotency key after storage recovers.

Highest-risk independent checks are cross-tenant presigned URL/object access, wrong magic bytes,
hash and size mismatch, scanner unavailability, concurrent completion/idempotency claims, duplicate
broker delivery, publish-before-ack crash, pool scope reuse, poison messages, and retry exhaustion.
