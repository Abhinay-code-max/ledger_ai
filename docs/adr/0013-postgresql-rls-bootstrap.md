# ADR 0013: Transaction-local RLS with a narrow membership bootstrap

- Status: Accepted and implemented in Phase 1.
- Context: Normal tenant policies cannot resolve an identity's membership before tenant context
  exists, while broad runtime bypass would destroy the isolation boundary.
- Decision: A fixed-`search_path`, `SECURITY DEFINER` SQL function accepts verified issuer/subject,
  workspace code, and optional scope selectors. It returns one active membership plus effective
  roles and permissions. The runtime role can execute only this function, cannot read principals,
  is not a table owner, and has neither superuser nor `BYPASSRLS`. The application then applies
  `app.tenant_id` with transaction-local `set_config` before repository access.
- Threat model: Parameters are bound, selectors are verified inside the function, revoked or
  expired membership is excluded, only stable identifiers and authorization codes are returned,
  and every later query remains explicitly scoped and RLS-protected. Function ownership and source
  changes require security review.
- Consequences: Connection return clears context at transaction end; direct runtime queries fail
  closed without context. Migration ownership remains privileged and cannot be used by the app.
