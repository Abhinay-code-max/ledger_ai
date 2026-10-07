"""LedgerAI FastAPI application factory."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from ledgerai_backend import __version__
from ledgerai_backend.adapters.queue import CeleryJobQueue
from ledgerai_backend.adapters.scanner import DeterministicMalwareScanner
from ledgerai_backend.adapters.storage import S3ObjectStorage
from ledgerai_backend.core.config import Settings, get_settings
from ledgerai_backend.core.errors import (
    ApiError,
    api_error_handler,
    error_response,
    unexpected_error_handler,
    validation_error_handler,
)
from ledgerai_backend.core.identity import (
    AuthenticationError,
    IdentityProviderPort,
    JwtIdentityProvider,
)
from ledgerai_backend.core.logging import configure_logging
from ledgerai_backend.core.request_context import safe_external_id
from ledgerai_backend.database.engine import create_engine
from ledgerai_backend.database.session import create_session_factory
from ledgerai_backend.health.routes import router as health_router
from ledgerai_backend.ingestion.routes import router as ingestion_router
from ledgerai_backend.integration.adapters import (
    AdapterSecurity,
    Role1Adapter,
    Role2Adapter,
    Role3Adapter,
    Role6Adapter,
    SignedServiceTokenProvider,
)
from ledgerai_backend.integration.routes import router as integration_router
from ledgerai_backend.ports import JobQueuePort, MalwareScannerPort, ObjectStoragePort
from ledgerai_backend.tenancy.routes import router as tenancy_router


class UnconfiguredIdentityProvider:
    async def verify(self, token: str) -> Any:
        raise AuthenticationError


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | None = None,
    identity_provider: IdentityProviderPort | None = None,
    object_storage: ObjectStoragePort | None = None,
    malware_scanner: MalwareScannerPort | None = None,
    job_queue: JobQueuePort | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    owns_engine = engine is None and settings.database_dsn is not None
    if owns_engine:
        engine = create_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        for adapter in getattr(app.state, "role_adapters", {}).values():
            await adapter.aclose()
        if owns_engine and app.state.engine is not None:
            await app.state.engine.dispose()

    app = FastAPI(
        title="LedgerAI Backend",
        version=settings.service_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine) if engine else None
    if object_storage is not None:
        app.state.object_storage = object_storage
    elif settings.storage_endpoint_url:
        app.state.object_storage = S3ObjectStorage(settings)
    else:
        app.state.object_storage = None
    if malware_scanner is not None:
        app.state.malware_scanner = malware_scanner
    elif settings.scanner_adapter == "deterministic" and settings.environment != "production":
        app.state.malware_scanner = DeterministicMalwareScanner()
    else:
        app.state.malware_scanner = None
    if job_queue is not None:
        app.state.job_queue = job_queue
    elif settings.redis_url:
        app.state.job_queue = CeleryJobQueue(settings)
    else:
        app.state.job_queue = None
    app.state.role_adapters = {}
    if settings.service_token_secret:
        token_provider = SignedServiceTokenProvider(
            issuer=settings.service_token_issuer,
            subject=settings.service_name,
            secret=settings.service_token_secret.get_secret_value(),
        )
        adapter_types = {
            "role1": (settings.role1_base_url, Role1Adapter),
            "role2": (settings.role2_base_url, Role2Adapter),
            "role3": (settings.role3_base_url, Role3Adapter),
            "role6": (settings.role6_base_url, Role6Adapter),
        }
        for role, (base_url, adapter_type) in adapter_types.items():
            if base_url:
                app.state.role_adapters[role] = adapter_type(
                    AdapterSecurity(
                        base_url=base_url,
                        audience=f"ledgerai-{role}",
                        environment=settings.environment,
                        total_timeout=settings.adapter_total_timeout_seconds,
                        maximum_response_bytes=settings.adapter_max_response_bytes,
                    ),
                    token_provider,
                )
    if identity_provider is not None:
        app.state.identity_provider = identity_provider
    elif (
        settings.jwt_issuer
        and settings.jwt_audience
        and (settings.jwks_url or settings.jwt_public_key)
    ):
        app.state.identity_provider = JwtIdentityProvider(settings)
    else:
        app.state.identity_provider = UnconfiguredIdentityProvider()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Correlation-ID",
            "X-Workspace-Code",
            "X-Organization-ID",
            "X-Legal-Entity-ID",
            "Idempotency-Key",
            "If-Match",
        ],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.middleware("http")
    async def request_controls(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = safe_external_id(request.headers.get("X-Request-ID"))
        request.state.correlation_id = safe_external_id(request.headers.get("X-Correlation-ID"))
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > settings.max_request_bytes
            except ValueError:
                too_large = True
            if too_large:
                return error_response(
                    request,
                    status_code=413,
                    category="INPUT_VALIDATION",
                    code="REQUEST_TOO_LARGE",
                    message="The request is too large.",
                )
        try:
            async with asyncio.timeout(settings.request_timeout_seconds):
                response = await call_next(request)
        except TimeoutError:
            response = error_response(
                request,
                status_code=504,
                category="DOWNSTREAM",
                code="REQUEST_TIMEOUT",
                message="The request timed out.",
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return response

    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.include_router(health_router)

    @app.get("/version")
    async def version() -> dict[str, str]:
        return {"service": settings.service_name, "version": __version__}

    app.include_router(tenancy_router, prefix="/api/v1", tags=["workspace"])
    app.include_router(ingestion_router, prefix="/api/v1", tags=["ingestion"])
    app.include_router(integration_router, prefix="/api/v1", tags=["integration", "review"])
    return app


app = create_app()
