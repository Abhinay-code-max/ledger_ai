# ADR 0010: OpenTelemetry-compatible correlated observability

- Status: Accepted architecture; implementation deferred
- Context: Cross-role asynchronous work needs traceable results without placing sensitive evidence in telemetry.
- Decision: Traces, metrics, and structured logs use OpenTelemetry-compatible conventions and shared request/correlation/causation IDs.
- Consequences: Flows can be connected across components; teams must propagate identifiers and apply redaction consistently.
- Alternatives considered: Unstructured logs (hard to correlate); vendor-only instrumentation (lock-in); payload logging (sensitive-data risk).
- Deferred production concerns: Collector/vendor, sampling, cardinality budgets, retention, redaction validation, alerting, and access controls.

