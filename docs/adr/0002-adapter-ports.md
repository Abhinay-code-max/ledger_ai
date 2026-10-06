# ADR 0002: Adapter ports for independent systems

- Status: Accepted for hackathon Phase 0
- Context: Other roles and compute-heavy components must evolve independently.
- Decision: Integrate independently owned or compute-heavy systems through typed adapter ports using shared contracts.
- Consequences: Implementations are replaceable and fixtures can stand in for services; adapters add explicit mapping work.
- Alternatives considered: Direct imports or table access (tight coupling); provider-specific SDKs in domain modules (lock-in).
- Deferred production concerns: Network timeouts, bulkheads, circuit breakers, provider qualification, and capacity contracts.

