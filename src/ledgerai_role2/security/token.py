"""Service token verification and claim binding for Role 2."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import jwt


class ServiceAuthenticationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ServiceAuthorizationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def verify_service_token(
    token: str,
    *,
    secret: str,
    expected_audience: str = "role2",
    expected_issuer: str | None = "ledgerai-backend",
    expected_tenant_id: UUID | None = None,
    expected_operation_id: UUID | None = None,
    clock_skew_seconds: int = 5,
) -> dict[str, Any]:
    """Decode and validate short-lived, audience-bound service token."""
    if not token or not token.strip():
        raise ServiceAuthenticationError("MISSING_TOKEN", "Authorization token is missing.")

    options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_iat": True,
        "verify_aud": bool(expected_audience),
        "verify_iss": bool(expected_issuer),
        "require": ["exp", "iat", "aud", "iss", "tenant_id", "operation_id"],
    }

    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=expected_audience,
            issuer=expected_issuer,
            leeway=clock_skew_seconds,
            options=options,  # type: ignore[arg-type]
        )
    except jwt.ExpiredSignatureError as exc:
        raise ServiceAuthenticationError("TOKEN_EXPIRED", "Service token has expired.") from exc
    except jwt.InvalidAudienceError as exc:
        raise ServiceAuthenticationError("INVALID_AUDIENCE", "Token audience mismatch.") from exc
    except jwt.InvalidIssuerError as exc:
        raise ServiceAuthenticationError("INVALID_ISSUER", "Token issuer mismatch.") from exc
    except jwt.PyJWTError as exc:
        raise ServiceAuthenticationError("INVALID_TOKEN", "Service token is invalid.") from exc

    # Validate bound tenant_id
    token_tenant = claims.get("tenant_id")
    if not token_tenant:
        raise ServiceAuthenticationError("MISSING_TENANT_CLAIM", "Token missing tenant_id claim.")
    if expected_tenant_id is not None and str(expected_tenant_id) != str(token_tenant):
        raise ServiceAuthorizationError(
            "TENANT_MISMATCH",
            f"Token tenant_id '{token_tenant}' does not match '{expected_tenant_id}'.",
        )

    # Validate bound operation_id
    token_operation = claims.get("operation_id")
    if not token_operation:
        raise ServiceAuthenticationError(
            "MISSING_OPERATION_CLAIM", "Token missing operation_id claim."
        )
    if expected_operation_id is not None and str(expected_operation_id) != str(token_operation):
        raise ServiceAuthorizationError(
            "OPERATION_MISMATCH",
            f"Token operation_id '{token_operation}' does not match '{expected_operation_id}'.",
        )

    return claims
