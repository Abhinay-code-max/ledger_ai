"""Minimal OpenTelemetry-compatible span helpers."""

from opentelemetry import trace

tracer = trace.get_tracer("ledgerai.backend")
