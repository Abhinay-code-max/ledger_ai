# ADR 0004: PostgreSQL as authoritative operational store

- Status: Accepted architecture; implementation deferred
- Context: Operational state will require transactions, constraints, querying, and reliable outbox writes.
- Decision: PostgreSQL will be the authoritative operational store when persistence is implemented.
- Consequences: Strong transactional semantics and familiar tooling; schema and migration governance will be required.
- Alternatives considered: Document database (weaker fit for relational invariants); in-memory state (not durable); object storage as database (poor transactions).
- Deferred production concerns: Schema design, migrations, tenancy enforcement, encryption, backup/restore, HA, retention, and connection pooling.

