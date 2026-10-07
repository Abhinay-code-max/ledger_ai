# ADR 0008: SSE for one-way frontend progress

- Status: Accepted architecture; implementation deferred
- Context: Job progress primarily flows from server to browser and does not demonstrate bidirectional streaming needs.
- Decision: Use Server-Sent Events for one-way progress; require evidence before adopting WebSockets.
- Consequences: Simpler HTTP operation and reconnection semantics; client-to-server actions remain ordinary requests.
- Alternatives considered: WebSockets (unneeded bidirectional complexity); polling (latency and load); broker exposure to browsers (security boundary violation).
- Deferred production concerns: Proxy buffering, connection limits, resume IDs, authorization refresh, fan-out, and degraded polling fallback.

