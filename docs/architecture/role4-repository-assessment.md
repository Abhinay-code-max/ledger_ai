# Role 4 repository assessment — Phase 0

Status: verified on 2026-10-05 before Phase 0 edits.

## Verified facts

- The supplied workspace directory was empty and was not a Git repository. There was no branch,
  history, remote, worktree state, `AGENTS.md`, contributor guide, README, ownership file, source,
  schema, database model, event definition, CI configuration, or package-manager file.
- Therefore there was no existing team code to modify or reuse and no team-agreed base branch to
  identify. The intended `role4/backend-orchestration` branch could not safely be created.
- Python 3.14.4, Pydantic 2.13.4, pytest 9.1.1, and jsonschema 4.26.0 were available locally.
  Ruff and mypy executables were not initially installed.

## Phase 0 structure established

- `src/ledgerai_contracts/v1/`: canonical Pydantic v2 contract source.
- `shared/schemas/v1/`: generated JSON Schema artifacts; never edit these by hand.
- `shared/fixtures/contracts/v1/`: deterministic, synthetic NOVA examples.
- `tools/generate_contract_artifacts.py`: validation and deterministic generation.
- `tests/`: contract, fixture, version, safety, and invariant checks.
- `docs/adr/`: control-plane architecture decisions.
- `docs/integration/`: cross-role use and compatibility guidance.
- `.github/workflows/contracts.yml`: isolated contract validation job.

Role 4 may safely modify the paths above. Future implementation code should live outside the
contract package (recommended: `src/ledgerai_backend/`) so importing contracts never initializes a
server or infrastructure client. Shared contract changes require cross-role review.

## Ownership boundaries

Only Role 4's name and scope were provided by verified input. The following is a **proposed,
unconfirmed boundary**, not a claim about existing team assignments:

| Role | Proposed boundary | Must not own through this package |
|---|---|---|
| 1 | Document ingestion and extraction adapters | Accounting validation or posting |
| 2 | Deterministic accounting calculation, journal validation and posting | AI evidence interpretation |
| 3 | Reconciliation algorithms and exception detection | Final approval or posting |
| 4 | Contract governance, orchestration ports, policy/approval flow integration, jobs/events/errors | Other roles' algorithms or UI |
| 5 | User interface and human-review experience | Internal tables or server implementation details |
| 6 | Identity/platform/observability integration and release operations | Custom password storage or accounting policy decisions |

Each role lead must confirm or correct this table. Until then, logical producer/consumer labels in
the integration guide take precedence over assumptions about a role number.

## Missing foundations addressed

Phase 0 adds canonical types, generated schemas, fixtures, compatibility policy, ADRs, tests,
developer commands, and CI. It deliberately does not add API endpoints, database tables, queues,
auth flows, external clients, or business workflows.

## Conflict and inconsistency assessment

- There were no existing files, so there were no immediate merge-conflict zones or legacy
  architecture inconsistencies.
- Likely future conflict zones are the public contract exports, event type registry, schema and
  fixture directories, dependency metadata, and CI workflow. Changes there need Role 4 review.
- The lack of Git metadata means ownership enforcement, branch protection, and the intended branch
  remain unresolved.
- The role-number mapping, ID-provider choice, queue/event implementation, object-storage provider,
  database migration framework, retention/redaction policy, policy authoring ownership, and API
  versioning scheme require team coordination.

## Assumptions

- Python was selected because no language convention existed and the specification prefers
  Pydantic v2 for Python backends.
- All initial business fixtures are legal-entity scoped, so they use `EntityTenantContext`.
  `TenantContext` permits a missing legal entity only for future organization-level objects.
- Contract major v1 is represented by `schema_version: "1.0"`; event names also carry `.v1`.
- UUIDs are stable interchange identifiers. Opaque object keys are allowed; OS paths and signed
  storage URLs are not.

