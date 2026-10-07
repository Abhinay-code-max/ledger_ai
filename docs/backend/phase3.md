# Phase 3 service integration, policy, and review

Phase 3 connects accepted immutable document versions to independently owned Role 1, 2, 3,
and 6 services. Role 4 remains the control plane: external services provide evidence or
proposals, while Role 4 validates contracts, persists immutable versions, applies deterministic
policy, records human decisions, and emits at most one posting request.

## Workflow

The event sequence is `document.extraction.requested.v1`, `document.extracted.v1`,
`document.validated.v1`, `reconciliation.requested.v1`, `reconciliation.proposed.v1`, optional
`exception.created.v1`, `journal.proposal.created.v1`, `policy.evaluated.v1`, optional
`approval.requested.v1`, `approval.decided.v1`, and finally
`journal.posting.requested.v1`. The Phase 2 inbox/outbox remains the delivery boundary. Stable
job input references and unique database indexes deduplicate extraction work and posting handoff.
No Phase 3 state or event claims that a journal was posted.

## Service boundary

Each adapter has a configured base origin and fixed endpoint path. Production requires HTTPS and
all four real service URLs plus a dedicated service-token secret. Calls use short-lived,
audience-bound service tokens; client bearer tokens and storage credentials are never forwarded.
Redirects, compression, oversized responses, duplicate JSON keys, malformed JSON, unexpected
content types, unknown fields, wrong schema versions, wrong tenant contexts, and wrong workflow
references fail closed. Connect/read/write/pool/total timeouts, classified retries, deterministic
jitter, and a circuit breaker bound failure amplification. An uncertain timeout remains an unknown
outcome and retries use the same operation ID.

## Evidence and versioning

Extraction, match, exception, journal, policy-decision, and approval-action payloads are retained
as bounded JSON plus queryable columns. Extraction fields keep confidence and provenance.
External producer, model, prompt, and algorithm versions are explicit. Journal proposal lines use
fixed-precision positive amounts with an explicit direction and currency. Journal proposals are
constrained to `NOT_VALIDATED` and `UNPOSTED`; corrections must create a new version and the old
version remains historical.

## Deterministic extraction validation

Validation is separate from model inference. It checks required invoice fields, duplicate
conflicts, provenance, critical missing/low-confidence evidence, exact decimal arithmetic when
subtotal/tax/total exist, and external error issues. It never invents missing values and does not
claim legal, tax, GST, or accounting correctness. Outcomes are `VALIDATED`, `REVIEW_REQUIRED`,
`BLOCKED`, or `RETRYABLE_FAILURE`.

## Policy DSL

Policy conditions contain only an allowlisted field, one of `eq`, `ne`, `lt`, `lte`, `gt`, `gte`,
`in`, `not_in`, or `exists`, and a typed operand. Floats, unknown fields/operators, duplicate rule
IDs, and excessive rules/conditions are rejected. Rules are evaluated as an AND. Only the highest
matching priority participates; a tie resolves safely as `BLOCKED`, `ESCALATED`,
`REVIEW_REQUIRED`, then `AUTO_ELIGIBLE`. No match defaults to `REVIEW_REQUIRED`. There is no eval,
SQL, regex, template, import, shell, or model-generated rule execution. Published versions are
immutable, and decisions retain exact inputs, matched rule IDs, reasons, evaluator version, and
policy version for replay.

## Review and approval

Review APIs expose exceptions, reconciliation proposals, journal proposals, and approval requests
with tenant-scoped keyset pagination. Actions require an idempotency key, `If-Match` request
version, exact resource version, and action-specific permission. Reject, correct, evidence request,
and escalation require a reason; correction additionally requires allowlisted structured changes.
Rows are locked before transition, the first valid terminal action wins, expired and stale requests
fail, and maker-checker prevents self-approval. Actions are immutable.

Permissions are deliberately separated:

| Role | Read review evidence | Approve/reject/escalate | Correct/request evidence | Policy admin |
|---|---:|---:|---:|---:|
| Tenant administrator | yes | yes | yes | yes |
| Entity administrator | yes | yes | yes | yes |
| Accountant | yes | no | yes | no |
| Reviewer | yes | yes | request only | no |
| Operator | yes | no | no | no |
| Viewer | yes | no | no | no |

## Posting guard

A posting event requires an approved, active request bound to the exact non-superseded proposal
version; an `AUTO_ELIGIBLE` or reviewed `REVIEW_REQUIRED` policy decision; the original unposted,
not-validated state; present decision evidence; and no unresolved high/critical exception. A unique
partial outbox index makes retries and concurrent approvals produce one effective posting request.
Role 2 may return validation or acceptance evidence, but only Role 2 can later establish accounting
validation and Phase 3 never emits `journal.posted.v1`.

## Data security and operations

All 13 new tables carry tenant, organization, and legal-entity scope, composite tenant-aware
foreign keys, forced PostgreSQL RLS, bounded strings/JSON, and queue/status indexes. Immutable
tables grant the runtime role only `SELECT` and `INSERT`; mutable workflow tables omit `DELETE`.
Metrics may label only service, operation, outcome, circuit state, reason code, and policy version—
never tenant IDs, filenames, invoice/bank references, comments, tokens, or evidence.

Local verification uses PostgreSQL with the non-owner runtime role, Redis, and encrypted/versioned
MinIO. CI uses protocol-faithful local services and HTTP mock transports; it does not enable fake
production adapters. Run `uv sync --all-extras --frozen`, `alembic upgrade head`, and `pytest` with
the documented Phase 2 service environment variables.

## Known limitations and Phase 4 boundary

Role 1 inference, Role 2 accounting formulas/posting, Role 3 matching algorithms, Role 5 UI, Role 6
GPU optimization, financial statements, period close, and the complete audit/provenance service
remain outside Phase 3. Production owners must provision each real service URL, token trust,
certificates, routing, and downstream idempotency retention before deployment.
