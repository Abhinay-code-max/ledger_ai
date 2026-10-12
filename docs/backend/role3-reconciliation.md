# Role 3 reconciliation service

Role 3 proposes reconciliation evidence. It never approves a proposal, posts a journal, closes a
period, or writes another role's database. Its only write-like state is a bounded, process-local
idempotency cache keyed by `(tenant_id, operation_id)`.

## Boundary and Canonical v1 Wire Contract

Run the standalone ASGI app by calling `create_reconciliation_app(Role3Security(...))`. Role 4
calls `POST /v1/reconciliations` with the canonical request body and these headers:

- `Authorization: Bearer <short-lived HS256 service JWT>`
- `X-Operation-ID`, `X-Correlation-ID`
- `X-Tenant-ID`, `X-Organization-ID`, `X-Legal-Entity-ID`

### Canonical Service Audience

The integration configuration selected this canonical Role 3 audience:

```
ledgerai-role3
```

Role 3 enforces this exact audience strictly and fails closed on:
- `ledgerai:role3` (colon delimiter rejected)
- `role3`, `role1`, `role2`, `ledgerai-role6`
- missing `aud` claims or array audiences containing unauthorized values

The JWT must carry `iss: "ledgerai-backend"`, `aud: "ledgerai-role3"`, an allowed subject,
`tenant_id`, and `operation_id`. All HTTP headers, JWT claims, and payload contexts must agree.

### Wire Compatibility

The response model strictly satisfies Role 4's canonical `ReconciliationResult`:

```python
class ReconciliationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(pattern=r"^1\.0$")
    tenant_context: EntityTenantContext
    proposal: MatchProposal
    exceptions: list[ExceptionRecord] = Field(default_factory=list, max_length=100)
```

No undeclared fields are returned across the wire. The frozen canonical v1 `MatchProposal` and
`ExceptionRecord` schemas are preserved without modification.

Deterministic algorithm version (`reconciliation-deterministic/1.0.0`) and rule version
(`reconciliation-rules/1.0.0`) are preserved using fields already supported by canonical v1:
- `MatchProposal.producer.algorithm_version`
- `MatchProposal.producer.rule_or_policy_version`
- `ExceptionRecord.detector.algorithm_version`
- `ExceptionRecord.detector.rule_or_policy_version`
- `MatchProposal.correlation.request_id` (preserves `operation_id`)
- `ExceptionRecord.correlation.request_id` (preserves `operation_id`)

## Internal Domain Models and Translator

To provide explainable matching without violating the frozen canonical v1 wire surface, Role 3
maintains internal domain models in `ledgerai_backend.reconciliation.domain`:

1. `ConfidenceComponent`: deterministic breakdown of individual score weights and values.
2. `CandidateScore`: record references, total score, eligibility status, components, and conflicts.
3. `InternalMatchProposal`: includes `candidate_scores`, `confidence_components`, and `operation_id`.
4. `InternalExceptionRecord`: includes `blocks_posting`, `blocks_close`, `algorithm_version`, and `rule_version`.
5. `InternalReconciliationResult`: rich internal output container.

Dedicated adapter/translator functions map internal models into the canonical v1 wire contracts:
- `to_canonical_proposal(internal: InternalMatchProposal) -> MatchProposal`
- `to_canonical_exception(internal: InternalExceptionRecord) -> ExceptionRecord`
- `to_canonical_response(internal: InternalReconciliationResult) -> ReconciliationResponse`

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

## Complexity and Operational Limits

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

## Future v2 Proposal (Additive Contract Evolution)

When cross-role consensus is reached to update the wire schema, Role 3 proposes the following
additive enhancements in `ledgerai_contracts.v2`:

1. `MatchProposal.candidate_scores: list[CandidateScore]`:
   Allows upstream consumers (Role 4, UI) to inspect top ranked alternatives and component scores
   directly over the wire.
2. `MatchProposal.confidence_components: list[ConfidenceComponent]`:
   Provides per-proposal explainability on reference, amount, date, counterparty, and evidence scores.
3. `ExceptionRecord.blocks_posting: bool` and `ExceptionRecord.blocks_close: bool`:
   Replaces inferred severity/reason-code parsing with explicit blocking flags.
4. `MatchProposal.operation_id: UUID` and `ExceptionRecord.operation_id: UUID`:
   Direct top-level correlation attribute alongside `correlation.request_id`.

Until v2 is formally adopted, these properties remain internal to Role 3 domain models.

## Tuning and Versioning

Configuration lives in `config/reconciliation-strategies.v1.json`. Any change to a threshold,
weight, normalization rule, supported currency, grouping behavior, or exception policy requires a
new strategy/rule version. A code-path change requires a new algorithm version. Never reuse a
version string for changed behavior.

Supported currencies are AUD, CAD, EUR, GBP, INR, JPY, and USD. Adding a currency requires evidence
that its decimal/minor-unit policy is safe; the current absolute tolerance is intentionally global
and is a known limitation for currencies with differing minor units.

Regenerate and verify artifacts with:

```powershell
python tools/generate_contract_artifacts.py --check
python tools/generate_role3_artifacts.py --check
```

The Role 3 OpenAPI artifact is `shared/openapi/role3-v1.json`. The NOVA request, expected match
graph, labeled cases, and measured results are under `shared/fixtures/reconciliation/v1`.

## Fixture Measurements

`tools/generate_role3_artifacts.py` computes metrics from the committed labeled fixture, never from
unlabeled traffic. Version `reconciliation-labeled/1.0.0` currently contains six cases and measures
edge precision `1.0000`, edge recall `1.0000`, and ambiguity rate `0.1667`. These are synthetic
fixture measurements, not model or production-accuracy claims.

## Known Limitations

- Only one best proposal is returned per operation because that is the current Role 4 adapter
  contract. Unselected records are explicit exceptions; callers may split batches for more
  proposals.
- Counterparty matching is exact after bounded normalization; aliases and transliteration are not
  inferred.
- Group matching finds the first canonical exact-total group within its bound, not every possible
  partition.
- Partial-payment balance tracking is advisory and requires human review.
- Exchange-rate conversion, credit notes, fees, and netting are not inferred.
- In-memory idempotency cache is process-local; multi-replica deployments require Redis or DB store.
