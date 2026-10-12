"""Role 6 FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ledgerai_contracts.v1.errors import ErrorEnvelope, FieldError
from ledgerai_contracts.v1.model_runtime import ModelManifest
from ledgerai_role6.backend import (
    ConfigurationDrivenRealBackend,
    DeterministicInferenceBackend,
    InferenceBackendPort,
)
from ledgerai_role6.config import Role6Settings, get_role6_settings
from ledgerai_role6.manifest import load_and_verify_manifest
from ledgerai_role6.queue import RuntimeQueueManager
from ledgerai_role6.routes import router


def create_role6_app(
    settings: Role6Settings | None = None,
    *,
    manifest: ModelManifest | None = None,
    backend: InferenceBackendPort | None = None,
) -> FastAPI:
    """Create and configure Role 6 Model Gateway FastAPI application."""
    settings = settings or get_role6_settings()

    # Load default manifest if not provided
    if manifest is None:
        manifest_path = Path(settings.model_manifest_path)
        artifacts_dir = Path(settings.model_artifacts_dir)
        manifest = load_and_verify_manifest(
            manifest_path,
            artifacts_dir,
            verify_files_exist=False,
        )

    # Instantiate backend if not provided
    if backend is None:
        if settings.active_backend == "deterministic":
            backend = DeterministicInferenceBackend()
        elif settings.active_backend == "real_onnx":
            backend = ConfigurationDrivenRealBackend(
                configured_model=manifest.model_name,
                cpu_fallback=True,
            )
        else:
            backend = DeterministicInferenceBackend()

    queue_manager = RuntimeQueueManager(
        max_concurrency=settings.max_concurrency,
        max_queue_depth=settings.max_queue_depth,
        per_tenant_max_concurrency=settings.per_tenant_max_concurrency,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Initialize backend
        await backend.initialize(manifest)
        yield
        # Graceful shutdown
        queue_manager.shutdown()

    app = FastAPI(
        title="LedgerAI Role 6 Local Model Gateway",
        version=settings.service_version,
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.manifest = manifest
    app.state.backend = backend
    app.state.queue_manager = queue_manager
    app.state.idempotency_store = {}
    app.dependency_overrides[get_role6_settings] = lambda: settings

    @app.middleware("http")
    async def enforce_content_length(request: Request, call_next: Any) -> Any:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request content-length exceeds maximum allowed"},
                    )
            except ValueError:
                pass
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            FieldError(
                field=".".join(str(p) for p in err.get("loc", ())),
                code="INVALID_VALUE",
                message=err.get("msg", "Invalid value"),
            )
            for err in exc.errors()[:25]
        ]
        envelope = ErrorEnvelope(
            schema_version="1.0",
            category="INPUT_VALIDATION",
            code="REQUEST_VALIDATION_FAILED",
            message="Request validation failed",
            request_id=UUID("00000000-0000-0000-0000-000000000000"),
            correlation_id=UUID("00000000-0000-0000-0000-000000000000"),
            field_errors=fields,
        )
        return JSONResponse(status_code=422, content=envelope.model_dump(mode="json"))

    app.include_router(router)
    return app
