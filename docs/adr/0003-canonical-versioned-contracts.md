# ADR 0003: One canonical typed source for contracts

- Status: Accepted for hackathon Phase 0
- Context: Six workstreams need compatible payloads without coordinating runtime availability.
- Decision: Pydantic v2 models are canonical; JSON Schemas and fixtures are deterministic generated artifacts under major version v1.
- Consequences: Python and non-Python consumers share one definition; generated artifacts must stay current in CI.
- Alternatives considered: Handwritten duplicate schemas (drift); undocumented dictionaries (unsafe); schema-first tooling (unnecessary second system).
- Deferred production concerns: Registry publishing, multi-language client generation, deprecation telemetry, and signed releases.

