# Phase 0 pre-integration contract hardening

Status: Accepted on 2026-10-05 after independent adversarial review.

The directory remains outside the official Git repository, so these v1 changes correct the draft
before publication. They do not authorize Phase 1.

## Tightened draft guarantees

- Event type and typed payload share one canonical registry. Generated JSON Schema uses a variant
  for every registered event. Typed payload tenant context must equal the entity-scoped envelope;
  standard JSON Schema cannot compare values across paths, so the schema carries an explicit
  extension and Pydantic enforces equality.
- Every top-level contract requires `schema_version: "1.0"` from external input.
- Every approval action uses a version-required resource reference.
- Journal proposals can state only `UNPOSTED` and `NOT_VALIDATED`; Role 2 validation remains a
  separate future interface.
- Directed bank transactions and journal lines use positive exact decimal strings. Direction alone
  expresses debit or credit.
- Processing jobs enforce state metadata, retry, error, attempt, and timestamp consistency. JSON
  Schema covers presence/nullability; comparison invariants are declared and enforced by Pydantic.
- Extraction processing completion is independent from review disposition. Critical unresolved or
  invalid evidence requires review; optional missing evidence does not.
- External and field error messages reject common secret, stack trace, connection string, machine
  path, and structurally recognizable raw SQL leakage markers, and may carry an opaque internal
  diagnostic ID. Ordinary selection prose is allowed consistently in Python and JSON Schema.
  Schema filters are defense in depth, not a substitute for runtime exception sanitization.

## Compatibility impact

This hardening is breaking for consumers of the unpublished draft that omitted schema versions,
used zero/negative directed amounts, omitted approval resource versions, treated extraction status
as review disposition, emitted contradictory job metadata, or paired arbitrary event payloads.
Existing valid NOVA fixture paths and public top-level contract names are preserved.
