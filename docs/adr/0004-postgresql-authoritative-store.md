# ADR 0004: PostgreSQL as authoritative operational store

- Status: Accepted; Phase 1 foundation implemented
- Context: Operational state will require transactions, constraints, querying, and reliable outbox writes.
- Decision: PostgreSQL will be the authoritative operational store when persistence is implemented.
- Consequences: Strong transactional semantics and familiar tooling; schema and migration governance will be required.
- Alternatives considered: Document database (weaker fit for relational invariants); in-memory state (not durable); object storage as database (poor transactions).
- Phase 1 implementation: Alembic, typed SQLAlchemy models, composite tenant constraints,
  non-owner runtime access, transaction-local RLS, and pool-leak tests.
- Deferred production concerns: Managed hosting, encryption/key policy, backup/restore, HA,
  retention, capacity sizing, and production pool tuning.

