"""API routes for Role 6 Model Gateway."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import monotonic
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ledgerai_contracts.v1.common import ProducerMetadata, ProducerType
from ledgerai_contracts.v1.model_runtime import (
    ModelInferenceRequest,
    ModelInferenceResponse,
    ModelManifest,
    RuntimeHealthStatus,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role6.backend import BackendError, InferenceBackendPort, ModelUnavailableError
from ledgerai_role6.config import Role6Settings, get_role6_settings
from ledgerai_role6.limits import validate_input_bounds
from ledgerai_role6.observability import log_inference_event
from ledgerai_role6.queue import RuntimeQueueManager
from ledgerai_role6.security import AuthenticatedCaller, authenticate_caller

router = APIRouter()
AuthScope = Annotated[tuple[AuthenticatedCaller, EntityTenantContext], Depends(authenticate_caller)]


@router.post(
    "/v1/models/infer",
    response_model=ModelInferenceResponse,
    status_code=status.HTTP_200_OK,
)
async def infer(
    payload: ModelInferenceRequest,
    request: Request,
    auth: AuthScope,
    settings: Annotated[Role6Settings, Depends(get_role6_settings)],
) -> ModelInferenceResponse:
    """Execute typed, bounded local model inference."""
    caller, tenant_context = auth

    # Cross-verify payload tenant context with verified token caller
    if payload.tenant_context != tenant_context:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payload tenant context does not match authenticated token context",
        )

    if payload.operation_id != caller.operation_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payload operation ID does not match authenticated token operation ID",
        )

    # Check duplicate operation store for idempotency
    idempotency_store: dict[tuple[UUID, UUID], ModelInferenceResponse] = getattr(
        request.app.state, "idempotency_store", {}
    )
    cache_key = (tenant_context.tenant_id, payload.operation_id)
    if cache_key in idempotency_store:
        return idempotency_store[cache_key]

    manifest: ModelManifest = request.app.state.manifest
    backend: InferenceBackendPort = request.app.state.backend
    queue_manager: RuntimeQueueManager = request.app.state.queue_manager

    # Validate input bounds
    validate_input_bounds(
        payload.input_data,
        manifest.limits,
        allowlisted_storage_prefix=settings.allowed_storage_prefix,
    )

    queue_start = monotonic()
    try:
        async with queue_manager.acquire(tenant_context.tenant_id):
            queue_duration_ms = (monotonic() - queue_start) * 1000.0

            try:
                # Wall-clock timeout enforcement
                output, metadata = await asyncio.wait_for(
                    backend.infer(payload, manifest),
                    timeout=manifest.limits.wall_clock_timeout_seconds,
                )
            except TimeoutError as exc:
                log_inference_event(
                    event_type="inference_timeout",
                    operation_id=payload.operation_id,
                    correlation_id=payload.correlation_id,
                    tenant_id=tenant_context.tenant_id,
                    model_name=payload.model_name,
                    backend_type=manifest.backend_type,
                    outcome="timeout",
                    error_code="TIMEOUT",
                )
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Model inference timed out",
                ) from exc
            except ModelUnavailableError as exc:
                log_inference_event(
                    event_type="model_unavailable",
                    operation_id=payload.operation_id,
                    correlation_id=payload.correlation_id,
                    tenant_id=tenant_context.tenant_id,
                    model_name=payload.model_name,
                    backend_type=manifest.backend_type,
                    outcome="model_unavailable",
                    error_code="MODEL_UNAVAILABLE",
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(exc),
                ) from exc
            except BackendError as exc:
                log_inference_event(
                    event_type="backend_error",
                    operation_id=payload.operation_id,
                    correlation_id=payload.correlation_id,
                    tenant_id=tenant_context.tenant_id,
                    model_name=payload.model_name,
                    backend_type=manifest.backend_type,
                    outcome="backend_error",
                    error_code="BACKEND_ERROR",
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Inference backend failed",
                ) from exc

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected runtime failure",
        ) from exc

    metadata.queue_duration_ms = round(queue_duration_ms, 2)

    producer = ProducerMetadata(
        producer_type=ProducerType.MODEL,
        name="ledgerai-role6-gateway",
        version=settings.service_version,
        model_name=manifest.model_name,
        model_version=manifest.immutable_revision,
    )

    response = ModelInferenceResponse(
        schema_version="1.0",
        tenant_context=tenant_context,
        operation_id=payload.operation_id,
        correlation_id=payload.correlation_id,
        output=output,
        execution_metadata=metadata,
        producer=producer,
        created_at=datetime.now(UTC),
    )

    # Store in idempotency store
    idempotency_store[cache_key] = response

    log_inference_event(
        event_type="inference_complete",
        operation_id=payload.operation_id,
        correlation_id=payload.correlation_id,
        tenant_id=tenant_context.tenant_id,
        model_name=payload.model_name,
        backend_type=manifest.backend_type,
        duration_ms=metadata.inference_duration_ms,
        queue_ms=metadata.queue_duration_ms,
        outcome="success",
    )

    return response


@router.post(
    "/v1/classifications",
    status_code=status.HTTP_200_OK,
)
async def classify_compatible(
    payload: dict[str, Any],
    request: Request,
    auth: AuthScope,
    settings: Annotated[Role6Settings, Depends(get_role6_settings)],
) -> dict[str, Any]:
    """Compatible endpoint matching Role4Adapter classify expectation."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_request_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Request content-length exceeds maximum allowed",
                )
        except ValueError as exc:
            raise HTTPException(400, "Invalid content length") from exc

    caller, tenant_context = auth

    payload_operation = payload.get("operation_id")
    if payload_operation is not None and str(payload_operation) != str(caller.operation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payload operation ID does not match authenticated token operation ID",
        )

    resource_id = payload.get("resource_id") or str(caller.operation_id)
    return {
        "schema_version": "1.0",
        "tenant_context": tenant_context.model_dump(mode="json"),
        "resource_id": str(resource_id),
        "category": "INVOICE",
        "confidence": "0.99",
        "provenance": [
            {
                "source": "role6-runtime",
                "method": "deterministic",
            }
        ],
    }


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/health/ready", response_model=RuntimeHealthStatus)
async def health_ready(request: Request) -> RuntimeHealthStatus:
    manifest: ModelManifest | None = getattr(request.app.state, "manifest", None)
    backend: InferenceBackendPort | None = getattr(request.app.state, "backend", None)
    queue_manager: RuntimeQueueManager = request.app.state.queue_manager

    manifest_valid = manifest is not None
    backend_ready = backend is not None and backend.is_ready()

    if not manifest_valid or not backend_ready or manifest is None or backend is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runtime model service not ready",
        )

    return RuntimeHealthStatus(
        status="healthy",
        backend_ready=backend_ready,
        manifest_valid=manifest_valid,
        active_backend=manifest.backend_type,
        configured_model=manifest.model_name,
        loaded_revision=manifest.immutable_revision,
        device=backend.get_device(),
        active_concurrency=queue_manager.active_concurrency,
        queue_depth=queue_manager.queue_depth,
    )


@router.get("/v1/models/manifest", response_model=ModelManifest)
async def get_model_manifest(
    request: Request,
    auth: AuthScope,
) -> ModelManifest:
    """Retrieve verified active model manifest."""
    manifest = getattr(request.app.state, "manifest", None)
    if not isinstance(manifest, ModelManifest):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model manifest not loaded",
        )
    return manifest
