# Cross-role contracts v1

Canonical Python models are in `src/ledgerai_contracts/v1`; generated JSON Schemas are in
`shared/schemas/v1`; synthetic, de-identified NOVA fixtures are in
`shared/fixtures/contracts/v1`. Importing the package starts no backend and contacts no external
service.

## Commands

```powershell
python tools/generate_contract_artifacts.py
python tools/generate_contract_artifacts.py --check
pytest
```

To validate one fixture in Python, load its JSON and call the corresponding model's
`model_validate`. Non-Python consumers validate it against the matching JSON Schema.

## Producer and consumer map

This map is the Phase 0 integration proposal. Role-number ownership remains pending confirmation
because the starting repository contained no ownership evidence.

| Contract | Producer | Consumers | Important invariant |
|---|---|---|---|
| `DocumentMetadata` | Role 1 / intake | Roles 1, 3, 4, 5 | Immutable evidence reference; filename untrusted |
| `DocumentExtraction` | Role 1 | Roles 2, 3, 4, 5 | Processing status and review disposition are separate |
| `BankTransaction` | Role 3 / import adapter | Roles 2, 3, 4, 5 | Positive exact money; direction carries the sign |
| `MatchProposal` | Role 3 | Roles 2, 4, 5 | Proposal, never final reconciliation |
| `ExceptionRecord` | Roles 2 or 3 | Roles 4, 5 | Versioned detector and supporting evidence |
| `JournalProposal` | AI/classification adapter via Role 4 | Roles 2, 4, 5 | Always unposted; Role 2 alone validates accounting invariant |
| `PolicyDecision` | Versioned policy adapter via Role 4 | Roles 4, 5 | Reproducible evidence, not a Boolean permission |
| `ApprovalDecision` | Role 5 human review via Role 4 boundary | Roles 2, 4, 5 | Every action binds to one immutable resource version |
| `AuditEvent` | All services through Role 4 convention | Roles 4, 6 | No raw evidence, credentials, or needless sensitive data |
| `ProcessingJob` | Role 4 orchestration | Roles 1, 3, 5, 6 | Explicit retry/failure lifecycle |
| `EventEnvelope` | All producing roles | Roles 1–6 as subscribed | Event type is bound to a typed payload |
| `ErrorEnvelope` | All service boundaries | Primarily Role 5; all callers | Safe stable codes; no internal leakage |

Role 6's proposed identity/platform/observability responsibilities and every role assignment above
must be confirmed by the team. Logical interfaces remain usable even if role numbers change.

## Required integration behavior

- Carry tenant, organization, and legal-entity context on entity-scoped objects. An API must derive
  and authorize this context from membership; never trust a client tenant ID.
- Carry request and correlation IDs across a flow. `causation_id` points to the immediate triggering
  event or operation; events also have a globally unique `event_id`.
- Serialize money amounts as decimal strings. Never send a JSON number for money.
- Directed debit/credit records require amounts greater than zero. Zero, negative, signed,
  scientific, locale-formatted, integer, and floating-point inputs are invalid; direction is the
  only sign representation.
- Preserve producer/model/algorithm/rule/prompt versions and evidence provenance.
- Send `schema_version: "1.0"` explicitly on every top-level contract. Missing, malformed, and
  unsupported versions are rejected rather than defaulted.
- Reject unknown contract majors and safely handle documented error categories. Error messages
  are user-safe only and carry an optional internal error ID; runtime middleware must still
  sanitize exceptions.
- Do not read another role's database tables. Integrate only through these contracts and adapter
  ports.

All 17 v1 events are entity-scoped. The canonical event registry binds each `event_type` to one
payload model for Python and JSON Schema consumers. Payloads containing full tenant-scoped objects
must exactly match the envelope tenant, organization, and legal entity. Standard JSON Schema cannot
compare UUID equality across object paths, so the schema publishes
`x-ledgerai-tenant-context-invariant`; Pydantic enforces equality before routing. Reference-only
payloads use the envelope context as authoritative. There are no organization-scoped exceptions in
v1.

Extraction `status` describes processing only (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`).
`review_disposition` independently states `NOT_REQUIRED`, `REVIEW_REQUIRED`, or `REVIEWED`.
Critical low-confidence or missing evidence and critical `ERROR` validation issues require an
explicit review signal. Missing optional fields do not. Confidence remains evidence, never posting
authorization.

An approval applies only to `reviewed_resource.resource_version`. Approval, rejection,
correction, evidence requests, and escalation never transfer to another version; corrections create
a new proposal version. A `JournalProposal` must explicitly remain `UNPOSTED` and
`NOT_VALIDATED`; Role 2 produces any future deterministic validation result as a separate contract.

Processing-job schemas express state-specific presence and nullability conditions. Pydantic also
enforces timestamp ordering, remaining-attempt rules, and retry chronology that standard JSON
Schema cannot compare; these limitations are declared through schema extensions.

## Changing a contract

Open a coordinated change with: rationale, affected producers and consumers, compatibility
classification, canonical model edit, regenerated schema and fixtures, test updates, and migration
plan when breaking or deprecated. See `docs/architecture/contract-compatibility.md`. A breaking
change creates a new major directory/package; field meaning never changes silently.

