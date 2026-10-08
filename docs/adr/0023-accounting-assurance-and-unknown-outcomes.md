# ADR 0023: Accounting assurance and unknown outcomes

- Status: Accepted and implemented in Phase 4
- Context: Role 2 owns deterministic accounting validation, posting, period close, and statement calculation. A timeout after a mutating request does not prove that the operation failed; retrying it blindly can duplicate a journal or close.
- Decision: Role 4 assigns a stable operation ID and idempotency key before calling Role 2. `UNKNOWN` is a durable state. Recovery uses a dedicated Role 2 status lookup with the same operation ID and never resubmits the mutation. Confirmations, statement snapshots, audit events, provenance edges, and progress events are append-only and protected by PostgreSQL RLS and database triggers.
- Consequences: Operators can safely reconcile ambiguous outcomes. Role 2 must retain operation lookup records for at least the agreed idempotency window and must bind every response to tenant, operation, and resource identifiers.
- Alternatives considered: treating timeout as failure (unsafe duplicate risk); automatic mutation retry (unsafe); letting Role 4 calculate accounting results (violates ownership boundary).
