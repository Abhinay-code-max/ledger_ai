# ADR 0006: Hide asynchronous infrastructure behind interfaces

- Status: Accepted architecture; implementation deferred
- Context: Extraction, reconciliation, and posting requests may be long-running, but no broker is selected in Phase 0.
- Decision: Expose job-queue and event-bus ports; domain modules depend on interfaces and versioned envelopes, not broker SDKs.
- Consequences: Broker choice can change and tests use fixtures; delivery semantics must be made explicit later.
- Alternatives considered: Synchronous-only execution (poor long-task behavior); direct broker APIs throughout code (vendor coupling).
- Deferred production concerns: Broker choice, ordering, backpressure, partitions, replay, retention, poison messages, and operational dashboards.

