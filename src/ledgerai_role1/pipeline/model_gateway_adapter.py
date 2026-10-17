"""Adapter for communicating with Agent 1's real local model inference gateway (Role 6)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import jwt
from pydantic import BaseModel

from ledgerai_contracts.v1.model_runtime import (
    ModelInferenceRequest,
    ModelInferenceResponse,
    RuntimeHealthStatus,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class Role6InferenceGatewayError(Exception):
    """Raised when communication with Agent 1's inference gateway fails."""

    def __init__(
        self, message: str, status_code: int | None = None, error_code: str | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class Role6InferenceGatewayAdapter:
    """Client adapter for executing bounded, isolated inference against Role 6."""

    def __init__(
        self,
        base_url: str,
        secret: str,
        *,
        audience: str = "ledgerai-role6",
        issuer: str = "ledgerai-role1",
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.audience = audience
        self.issuer = issuer
        self.timeout = timeout_seconds
        self._client = client

    def _generate_service_token(
        self,
        tenant_context: EntityTenantContext,
        operation_id: UUID,
        *,
        subject: str = "role1-document-intelligence",
        lifetime_seconds: int = 60,
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "iss": self.issuer,
            "sub": subject,
            "aud": self.audience,
            "tenant_id": str(tenant_context.tenant_id),
            "organization_id": str(tenant_context.organization_id),
            "legal_entity_id": str(tenant_context.legal_entity_id),
            "operation_id": str(operation_id),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=lifetime_seconds)).timestamp()),
        }
        return jwt.encode(payload, self.secret, algorithm="HS256")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self.timeout)

    async def check_readiness(self) -> RuntimeHealthStatus:
        """Query the inference gateway's health and readiness endpoint."""
        url = f"{self.base_url}/health/ready"
        client = await self._get_client()
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise Role6InferenceGatewayError(
                    f"Gateway returned HTTP {resp.status_code}: {resp.text}",
                    status_code=resp.status_code,
                )
            return RuntimeHealthStatus.model_validate(resp.json())
        except httpx.RequestError as exc:
            raise Role6InferenceGatewayError(f"Gateway connection error: {exc}") from exc

    async def infer(
        self,
        *,
        request: ModelInferenceRequest | Mapping[str, Any],
        tenant_context: EntityTenantContext,
        operation_id: UUID,
        correlation_id: UUID | None = None,
    ) -> ModelInferenceResponse:
        """Submit typed inference request to the model runtime gateway."""
        url = f"{self.base_url}/v1/models/infer"
        token = self._generate_service_token(tenant_context, operation_id)
        cid = correlation_id or getattr(request, "correlation_id", operation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Tenant-ID": str(tenant_context.tenant_id),
            "X-Organization-ID": str(tenant_context.organization_id),
            "X-Legal-Entity-ID": str(tenant_context.legal_entity_id),
            "X-Operation-ID": str(operation_id),
            "X-Correlation-ID": str(cid),
        }

        body = request.model_dump(mode="json") if isinstance(request, BaseModel) else dict(request)

        client = await self._get_client()
        try:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code != 200:
                detail = resp.text
                error_code = "DOWNSTREAM_ERROR"
                try:
                    err_json = resp.json()
                    detail = err_json.get("detail", detail)
                    error_code = err_json.get("code", error_code)
                except Exception:
                    pass
                raise Role6InferenceGatewayError(
                    f"Gateway inference failed: {detail}",
                    status_code=resp.status_code,
                    error_code=error_code,
                )
            return ModelInferenceResponse.model_validate(resp.json())
        except httpx.RequestError as exc:
            raise Role6InferenceGatewayError(f"Gateway connection error: {exc}") from exc
