"""Signed service token verification and tenant context binding."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import SecretStr

from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role6.config import Role6Settings, get_role6_settings


class SecurityError(RuntimeError):
    """Internal security failure."""


@dataclass(frozen=True, slots=True)
class AuthenticatedCaller:
    issuer: str
    calling_service: str
    tenant_id: UUID
    operation_id: UUID


def verify_service_token(
    token: str,
    secret: SecretStr,
    *,
    expected_audience: str,
    allowed_issuers: list[str],
    allowed_services: list[str],
    now: int | None = None,
) -> AuthenticatedCaller:
    """Verify signed service token with audience, issuer, expiry, and tenant binding."""
    if not token or not token.strip():
        raise SecurityError("MISSING_TOKEN")

    current_time = now if now is not None else int(time.time())

    try:
        payload = jwt.decode(
            token,
            secret.get_secret_value(),
            algorithms=["HS256"],
            audience=expected_audience,
            options={
                "require": ["iss", "sub", "aud", "exp", "iat", "tenant_id", "operation_id"],
                "verify_exp": True,
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise SecurityError("TOKEN_EXPIRED") from exc
    except jwt.InvalidAudienceError as exc:
        raise SecurityError("WRONG_AUDIENCE") from exc
    except jwt.InvalidIssuerError as exc:
        raise SecurityError("WRONG_ISSUER") from exc
    except Exception as exc:
        raise SecurityError("INVALID_TOKEN") from exc

    issuer = payload.get("iss")
    calling_service = payload.get("sub")
    nbf = payload.get("nbf")

    if nbf is not None and current_time < nbf:
        raise SecurityError("TOKEN_NOT_YET_VALID")

    if issuer not in allowed_issuers:
        raise SecurityError("UNAUTHORIZED_ISSUER")

    if calling_service not in allowed_services:
        raise SecurityError("UNAUTHORIZED_CALLING_SERVICE")

    try:
        tenant_id = UUID(str(payload.get("tenant_id")))
        operation_id = UUID(str(payload.get("operation_id")))
    except Exception as exc:
        raise SecurityError("MALFORMED_TOKEN_CLAIMS") from exc

    return AuthenticatedCaller(
        issuer=str(issuer),
        calling_service=str(calling_service),
        tenant_id=tenant_id,
        operation_id=operation_id,
    )


async def authenticate_caller(
    settings: Annotated[Role6Settings, Depends(get_role6_settings)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    x_organization_id: Annotated[UUID | None, Header(alias="X-Organization-ID")] = None,
    x_legal_entity_id: Annotated[UUID | None, Header(alias="X-Legal-Entity-ID")] = None,
    x_operation_id: Annotated[UUID | None, Header(alias="X-Operation-ID")] = None,
    x_correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    x_causation_id: Annotated[UUID | None, Header(alias="X-Causation-ID")] = None,
) -> tuple[AuthenticatedCaller, EntityTenantContext]:
    """Dependency enforcing service token authentication and header context consistency."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    token = parts[1]
    secret = settings.service_token_secret or SecretStr("a" * 32)

    try:
        caller = verify_service_token(
            token,
            secret,
            expected_audience=settings.service_audience,
            allowed_issuers=settings.allowed_issuers,
            allowed_services=settings.allowed_calling_services,
        )
    except SecurityError as exc:
        code = str(exc)
        if code == "TOKEN_EXPIRED":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            ) from exc
        if code in {"WRONG_AUDIENCE", "UNAUTHORIZED_ISSUER", "UNAUTHORIZED_CALLING_SERVICE"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden service token",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from exc

    # Header tenant and operation binding verification
    if x_tenant_id is None or x_organization_id is None or x_legal_entity_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required tenant context headers",
        )

    if x_tenant_id != caller.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch between token and request headers",
        )

    if x_operation_id and x_operation_id != caller.operation_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation mismatch between token and request headers",
        )

    tenant_context = EntityTenantContext(
        tenant_id=x_tenant_id,
        organization_id=x_organization_id,
        legal_entity_id=x_legal_entity_id,
    )

    return caller, tenant_context
