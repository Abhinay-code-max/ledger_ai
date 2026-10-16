"""Authenticated HTTP boundary for the standalone Role 3 service."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException

from ledgerai_backend.reconciliation.contracts import ReconciliationRequest, ReconciliationResponse
from ledgerai_backend.reconciliation.engine import ReconciliationEngine, ReconciliationInputError
from ledgerai_backend.reconciliation.security import Role3Security, ServiceAuthenticationError


@dataclass(frozen=True, slots=True)
class _CachedResult:
    digest: str
    response: ReconciliationResponse


class TenantOperationStore:
    """Process-local idempotency guard; keys are always tenant scoped."""

    def __init__(self, maximum_entries: int = 10_000) -> None:
        if maximum_entries < 1 or maximum_entries > 100_000:
            raise ValueError("invalid idempotency cache bound")
        self._maximum_entries = maximum_entries
        self._values: dict[tuple[UUID, UUID], _CachedResult] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self, request: ReconciliationRequest, engine: ReconciliationEngine
    ) -> ReconciliationResponse:
        serialized = json.dumps(
            request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        digest = hashlib.sha256(serialized).hexdigest()
        key = (request.tenant_context.tenant_id, request.operation_id)
        async with self._lock:
            cached = self._values.get(key)
            if cached:
                if cached.digest != digest:
                    raise ReconciliationInputError(
                        "IDEMPOTENCY_CONFLICT",
                        "The operation ID was already used with a different immutable payload.",
                    )
                return cached.response.model_copy(deep=True)
            if len(self._values) >= self._maximum_entries:
                raise ReconciliationInputError(
                    "IDEMPOTENCY_CAPACITY_EXCEEDED",
                    "The bounded operation cache is at capacity; retry after expiry or restart.",
                )
            response = engine.reconcile(request)
            self._values[key] = _CachedResult(digest=digest, response=response)
            return response.model_copy(deep=True)


def create_reconciliation_app(
    security: Role3Security,
    *,
    engine: ReconciliationEngine | None = None,
    store: TenantOperationStore | None = None,
) -> FastAPI:
    app = FastAPI(
        title="LedgerAI Role 3 Reconciliation",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )
    configured_engine = engine or ReconciliationEngine()
    configured_store = store or TenantOperationStore()

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready")
    async def health_ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/v1/reconciliations", response_model=ReconciliationResponse)
    async def reconcile(
        payload: ReconciliationRequest,
        authorization: Annotated[str, Header(alias="Authorization")],
        operation_id: Annotated[UUID, Header(alias="X-Operation-ID")],
        correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
        tenant_id: Annotated[UUID, Header(alias="X-Tenant-ID")],
        organization_id: Annotated[UUID, Header(alias="X-Organization-ID")],
        legal_entity_id: Annotated[UUID, Header(alias="X-Legal-Entity-ID")],
    ) -> ReconciliationResponse:
        if not authorization.startswith("Bearer ") or len(authorization) > 8192:
            raise HTTPException(status_code=401, detail="service authentication required")
        try:
            security.authorize(
                authorization[7:],
                payload,
                operation_id=operation_id,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                organization_id=organization_id,
                legal_entity_id=legal_entity_id,
            )
        except ServiceAuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        try:
            return await configured_store.execute(payload, configured_engine)
        except ReconciliationInputError as exc:
            status = 409 if exc.code == "IDEMPOTENCY_CONFLICT" else 422
            raise HTTPException(
                status_code=status, detail={"code": exc.code, "message": exc.message}
            ) from exc

    return app


def create_app() -> FastAPI:
    """Factory to run the standalone Role 3 reconciliation service."""
    import os

    secret = os.environ.get(
        "LEDGERAI_SERVICE_TOKEN_SECRET", "local-service-token-secret-32-chars-minimum"
    )
    security = Role3Security(secret=secret)
    return create_reconciliation_app(security)
