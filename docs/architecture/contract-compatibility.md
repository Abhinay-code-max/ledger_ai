# Contract compatibility policy

Role 4 owns coordination of shared contract evolution. Consumers must validate documented fields,
ignore additive optional fields where their decoder permits it, and never depend on generated or
undocumented data.

- Breaking changes require a new major contract version. Unknown majors are rejected safely.
- Adding a required field, removing a field, narrowing accepted values, or changing field meaning,
  units, tenant scope, ID semantics, or money representation is breaking.
- Additive optional fields may remain in the current major version.
- Enum additions require explicit consumer review because exhaustive switches can break.
- Money remains `{amount: decimal-string, currency: uppercase-three-letter-code}`. Floating-point
  input is never compatible.
- Deprecated fields require a documented replacement and migration window before removal in a new
  major version.
- Canonical models, generated schemas, fixtures, and tests change together. Generated files are not
  hand-edited.
- Cross-role changes require Role 4 coordination and affected producer/consumer review.
- `schema_version` is always explicit. Missing versions are invalid and are never interpreted as
  the newest supported contract.

Contract version describes wire-shape compatibility. It is independent of a resource/proposal
version (immutable business revision), model or algorithm version (producer provenance), policy or
rule version (decision reproducibility), and API version (transport endpoint lifecycle). Matching
numbers between these version systems imply nothing.

The Phase 0 v1 artifacts were not yet integrated into an official repository when independent
testing found unsafe ambiguity. The tenant, event-discriminator, version-requiredness, approval,
directed-money, job-state, and extraction-review corrections are therefore treated as
pre-integration hardening. They are validation-tightening changes that consumers of the earlier
draft must adopt before repository integration.

