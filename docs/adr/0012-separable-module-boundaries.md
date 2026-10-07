# ADR 0012: Preserve separable module boundaries

- Status: Accepted
- Context: Hackathon speed favors a modular monolith, while growth may demand independent services.
- Decision: Modules own behavior behind ports, exchange public versioned contracts, and never reach into another module's tables.
- Consequences: Later extraction is feasible; duplication of private domain models is preferable to leaking persistence internals.
- Alternatives considered: Shared database model imports (fast initially, hard to separate); immediate services (premature operations burden).
- Deferred production concerns: Boundary fitness tests, service extraction criteria, data ownership migration, API gateways, and distributed consistency.
