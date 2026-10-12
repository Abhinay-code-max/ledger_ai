"""Safe structured logging for Role 6 runtime - strictly redacting sensitive tokens and data."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from ledgerai_contracts.v1.model_runtime import ModelBackendType

logger = logging.getLogger("ledgerai_role6")


def log_inference_event(
    *,
    event_type: str,
    operation_id: UUID,
    correlation_id: UUID,
    tenant_id: UUID,
    model_name: str,
    backend_type: ModelBackendType | str,
    duration_ms: float | None = None,
    queue_ms: float | None = None,
    outcome: str = "success",
    error_code: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log structured execution telemetry without prompts, tokens, or document content."""
    payload: dict[str, Any] = {
        "event_type": event_type,
        "operation_id": str(operation_id),
        "correlation_id": str(correlation_id),
        "tenant_id": str(tenant_id),
        "model_name": model_name,
        "backend": str(backend_type),
        "outcome": outcome,
    }
    if duration_ms is not None:
        payload["duration_ms"] = round(duration_ms, 2)
    if queue_ms is not None:
        payload["queue_ms"] = round(queue_ms, 2)
    if error_code is not None:
        payload["error_code"] = error_code

    # Sanitize extra fields to forbid prompts, tokens, content
    if extra:
        forbidden_keys = {
            "token",
            "authorization",
            "secret",
            "prompt",
            "document_text",
            "text_content",
            "raw_completion",
            "fields",
            "content",
            "document",
        }
        for k, v in extra.items():
            if k.lower() not in forbidden_keys:
                payload[k] = v

    logger.info("inference_event: %s", payload)
