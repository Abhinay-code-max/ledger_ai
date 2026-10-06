# ADR 0007: Transactional outbox and consumer inbox

- Status: Accepted architecture; implementation deferred
- Context: Database changes and event publication cannot be atomically committed across independent systems.
- Decision: Use a transactional outbox for publication and a consumer inbox/deduplication record keyed by event ID.
- Consequences: At-least-once delivery becomes safe for idempotent consumers; storage and cleanup complexity increase.
- Alternatives considered: Dual writes (lost or phantom events); distributed transactions (operational complexity); best-effort publish (insufficient traceability).
- Deferred production concerns: Relay leasing, ordering keys, deduplication retention, replay controls, lag alerts, and disaster recovery.

