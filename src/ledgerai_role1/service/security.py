"""Security authentication and authorization middleware for Role 1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Header, HTTPException, Request, status

from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role1.service.config import Role1Settings


@dataclass(frozen=True, slots=True)
class AuthenticatedRoleContext:
    tenant_context: EntityTenantContext
    operation_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    issuer: str
    subject: str


def validate_object_reference(object_key: str, allowlisted_prefix: str) -> None:
    """Validate that an immutable object reference is secure and not traversing paths."""
    if not object_key or not isinstance(object_key, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Object key must be a non-empty string",
        )
    if (
        ".." in object_key
        or "\\" in object_key
        or object_key.startswith(("/", "file:", "http:", "https:"))
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or hostile object reference path",
        )
    if not re.match(r"^[A-Za-z0-9._/-]+$", object_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Object reference contains disallowed characters",
        )


async def authenticate_service_request(
    request: Request,
    authorization: str = Header(..., description="Bearer service JWT"),
    x_tenant_id: str = Header(..., description="Tenant UUID"),
    x_organization_id: str = Header(..., description="Organization UUID"),
    x_legal_entity_id: str = Header(..., description="Legal Entity UUID"),
    x_operation_id: str = Header(..., description="Operation UUID"),
    x_correlation_id: str = Header(..., description="Correlation UUID"),
    x_causation_id: str | None = Header(None, description="Causation UUID"),
) -> AuthenticatedRoleContext:
    """Validate Role 4 service JWT token and correlation headers."""
    settings = getattr(request.app.state, "settings", None) or Role1Settings()

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format; Bearer token required",
        )

    token = authorization[len("Bearer ") :].strip()

    try:
        tenant_uuid = UUID(x_tenant_id)
        org_uuid = UUID(x_organization_id)
        legal_entity_uuid = UUID(x_legal_entity_id)
        operation_uuid = UUID(x_operation_id)
        correlation_uuid = UUID(x_correlation_id)
        causation_uuid = UUID(x_causation_id) if x_causation_id else None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed UUID in correlation headers: {e}",
        ) from e

    try:
        payload = jwt.decode(
            token,
            settings.service_token_secret.get_secret_value(),
            algorithms=["HS256"],
            audience=settings.audience,
            options={"require": ["exp", "iat", "aud", "tenant_id", "operation_id"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service token has expired",
        ) from e
    except jwt.InvalidAudienceError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service token audience mismatch",
        ) from e
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Service token verification failed: {e}",
        ) from e

    # Verify claim binding to headers
    token_tenant = payload.get("tenant_id")
    if token_tenant != str(tenant_uuid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant ID in token does not match X-Tenant-ID header",
        )

    token_operation = payload.get("operation_id")
    if token_operation != str(operation_uuid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation ID in token does not match X-Operation-ID header",
        )

    tenant_context = EntityTenantContext(
        tenant_id=tenant_uuid,
        organization_id=org_uuid,
        legal_entity_id=legal_entity_uuid,
    )

    return AuthenticatedRoleContext(
        tenant_context=tenant_context,
        operation_id=operation_uuid,
        correlation_id=correlation_uuid,
        causation_id=causation_uuid,
        issuer=str(payload.get("iss", "unknown")),
        subject=str(payload.get("sub", "unknown")),
    )
