# ADR 0010: OpenTelemetry-compatible correlated observability

- Status: Accepted; Phase 1 correlation and logging foundation implemented
- Context: Cross-role asynchronous work needs traceable results without placing sensitive evidence in telemetry.
- Decision: Traces, metrics, and structured logs use OpenTelemetry-compatible conventions and shared request/correlation/causation IDs.
- Consequences: Flows can be connected across components; teams must propagate identifiers and apply redaction consistently.
- Alternatives considered: Unstructured logs (hard to correlate); vendor-only instrumentation (lock-in); payload logging (sensitive-data risk).
- Phase 1 implementation: UUID request/correlation propagation, structured JSON logs, recursive
  secret redaction, opaque internal error IDs, and vendor-neutral OpenTelemetry API hooks.
- Deferred production concerns: Collector/vendor, sampling, metrics, cardinality budgets,
  retention, alerting, and telemetry access controls.

