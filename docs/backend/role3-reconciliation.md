# Role 3 reconciliation service

Role 3 proposes reconciliation evidence. It never approves a proposal, posts a journal, closes a
period, or writes another role's database. Its only write-like state is a bounded, process-local
idempotency cache keyed by `(tenant_id, operation_id)`.

## Boundary

Run the standalone ASGI app by calling `create_reconciliation_app(Role3Security(...))`. Role 4
calls `POST /v1/reconciliations` with the canonical request body and these headers:

- `Authorization: Bearer <short-lived HS256 service JWT>`
- `X-Operation-ID`, `X-Correlation-ID`
- `X-Tenant-ID`, `X-Organization-ID`, `X-Legal-Entity-ID`

The JWT must have issuer `ledgerai-backend`, audience `ledgerai-role3`, an allowed service subject,
and matching `tenant_id` and `operation_id` claims. The header, claim, and body contexts must all
agree. Unknown fields, unsupported schema versions, foreign tenants, mixed legal entities, invalid
money strings, and reused operation IDs with changed payloads fail closed.

The response is deliberately compatible with Role 4's existing `ReconciliationResult`: one best
`proposal` plus up to 100 canonical `ExceptionRecord` objects. Input and output resources are bound
to immutable versions. Blocking exceptions change an otherwise proposed match to
`REVIEW_REQUIRED`.

## Strategy `reconciliation-rules/1.0.0`

Algorithm: `reconciliation-deterministic/1.0.0`.

Candidate scoring is deterministic and decimal-only:

| Component | Weight | Rule |
|---|---:|---|
| normalized exact reference | 0.40 | Unicode alphanumeric case-folded equality |
| amount | 0.30 | same currency and absolute difference at most `0.01` |
| date | 0.15 | inclusive 7-day window; linear decay inside the window |
| normalized exact party | 0.10 | Unicode alphanumeric case-folded equality |
| complete evidence | 0.05 | invoice flag plus invoice and bank provenance |

The one-to-one eligibility threshold is `0.70`. Currency, direction, date-window, and amount
conflicts are hard controls regardless of score. Two eligible candidates within `0.05` are
ambiguous and require human review. Semantic embeddings and model rankers are not used.

If no one-to-one candidate is eligible, the engine searches exact-total one-to-many and
many-to-one groups. Group size is limited to 5 and only same-currency, expected-direction,
in-window records enter the search. Reference-aligned amount differences become `PARTIAL` proposals
requiring review. All remaining records receive explicit unmatched exceptions.

## Complexity and operational limits

| Limit | Value |
|---|---:|
| invoices per operation | 500 |
| transactions per operation | 500 |
| candidates per record | 100 |
| evaluated pair edges | 10,000 |
| grouped records | 5 |
| group combinations | 10,000 |
| response candidates | 100 |
| response exceptions | 100 |
| idempotency cache entries per process | 10,000 |

Requests exceeding a bound are rejected with a stable code rather than partially evaluated.
Normalization is a linear scan over schema-bounded strings; no user-provided regular expression or
unbounded fuzzy search is executed. The service emits no raw narration, reference, party, or bank
account data to logs.

The in-memory idempotency cache is suitable for one process and deterministic replay tests. A
production multi-replica deployment should provide an atomic tenant-scoped external operation
store with TTL while preserving the same digest-conflict semantics.

## Tuning and versioning

Configuration lives in `config/reconciliation-strategies.v1.json`. Any change to a threshold,
weight, normalization rule, supported currency, grouping behavior, or exception policy requires a
new strategy/rule version. A code-path change requires a new algorithm version. Never reuse a
version string for changed behavior.

Supported currencies are AUD, CAD, EUR, GBP, INR, JPY, and USD. Adding a currency requires evidence
that its decimal/minor-unit policy is safe; the current absolute tolerance is intentionally global
and is a known limitation for currencies with differing minor units.

Regenerate and verify artifacts with:

```powershell
python tools/generate_contract_artifacts.py
python tools/generate_contract_artifacts.py --check
python tools/generate_role3_artifacts.py
python tools/generate_role3_artifacts.py --check
```

The Role 3 OpenAPI artifact is `shared/openapi/role3-v1.json`. The NOVA request, expected match
graph, labeled cases, and measured results are under `shared/fixtures/reconciliation/v1`.

## Fixture measurements

`tools/generate_role3_artifacts.py` computes metrics from the committed labeled fixture, never from
unlabeled traffic. Version `reconciliation-labeled/1.0.0` currently contains six cases and measures
edge precision `1.0000`, edge recall `1.0000`, and ambiguity rate `0.1667`. These are synthetic
fixture measurements, not model or production-accuracy claims.

## Known limitations

- Only one best proposal is returned per operation because that is the current Role 4 adapter
  contract. Unselected records are explicit exceptions; callers may split batches for more
  proposals.
- Counterparty matching is exact after bounded normalization; aliases and transliteration are not
  inferred.
- Group matching finds the first canonical exact-total group within its bound, not every possible
  partition.
- Partial-payment balance tracking is advisory and requires human review.
- Exchange-rate conversion, credit notes, fees, and netting are not inferred.
- The service authenticates with the repository's existing symmetric service-token convention.
  Independent key rotation or asymmetric workload identity is deployment follow-up work.
