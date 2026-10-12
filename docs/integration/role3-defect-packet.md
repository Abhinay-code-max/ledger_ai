# Role 3 integration defect packet

Status: blocking `integration/backend-e2e`

Source revision: `c8d778ed204fefd1cd45126a32aefd094b041480`

## Failure

Role 3 changes canonical v1 `MatchProposal` and `ExceptionRecord` wire contracts in a breaking
way. The changes add required fields (`operation_id`, version metadata, confidence components,
blocking flags), replace `ResourceReference` with `VersionedResourceReference`, and narrow several
collections. Existing valid v1 payloads and the Role 4 v1 adapter therefore fail validation.

This conflicts with `docs/architecture/contract-compatibility.md`: required fields, narrowed
accepted values, and changed ID/version semantics require a new major contract. Role 4 contracts
will not be weakened or silently redefined to accept the branch.

## Evidence

- Role 3 focused suite at the source revision: `26 passed`.
- Baseline Role 4 contract suite: `299 passed` before integration work.
- Diff reviewed:
  `18dce7558f6bd7136d53d0517d32542ae025f50b..c8d778ed204fefd1cd45126a32aefd094b041480`.
- Breaking files:
  `src/ledgerai_contracts/v1/reconciliation.py` and
  `src/ledgerai_contracts/v1/exceptions.py`.

## Required correction

Choose one coordinated resolution:

1. Preserve the published v1 required fields and return the existing canonical v1 response;
   keep Role 3 scoring details in a Role 3-internal model or add only reviewed optional fields.
2. Publish the new shape under a v2 package/schema/API path and provide an explicit Role 4
   compatibility adapter and migration plan.

Regenerate canonical schemas and fixtures from the corrected model, run Role 3 tests plus Role 4
contract tests, and report a new exact remote commit. Do not hand-edit generated schemas.
