"""Fail-closed authentication for Role 4 to Role 3 service calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt

from ledgerai_backend.reconciliation.contracts import ReconciliationRequest


class ServiceAuthenticationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Role3Security:
    secret: str
    issuer: str = "ledgerai-backend"
    audience: str = "ledgerai-role3"
    allowed_subjects: frozenset[str] = frozenset({"ledgerai-backend"})

    def __post_init__(self) -> None:
        if len(self.secret.encode()) < 32:
            raise ValueError("service token secret must be at least 32 bytes")
        if not self.allowed_subjects:
            raise ValueError("at least one service subject must be allowed")

    def authorize(
        self,
        token: str,
        request: ReconciliationRequest,
        *,
        operation_id: UUID,
        correlation_id: UUID,
        tenant_id: UUID,
        organization_id: UUID,
        legal_entity_id: UUID,
    ) -> None:
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub", "tenant_id", "operation_id"]
                },
            )
        except jwt.PyJWTError as exc:
            raise ServiceAuthenticationError("service authentication failed") from exc
        if claims.get("sub") not in self.allowed_subjects:
            raise ServiceAuthenticationError("service subject is not allowed")
        expected_context = request.tenant_context
        if (
            operation_id != request.operation_id
            or correlation_id != request.correlation_id
            or tenant_id != expected_context.tenant_id
            or organization_id != expected_context.organization_id
            or legal_entity_id != expected_context.legal_entity_id
            or claims.get("operation_id") != str(request.operation_id)
            or claims.get("tenant_id") != str(expected_context.tenant_id)
        ):
            raise ServiceAuthenticationError("authenticated request context mismatch")
