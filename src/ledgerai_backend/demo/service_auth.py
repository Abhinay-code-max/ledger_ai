"""Strict authentication and request binding shared by NOVA service stubs."""

from __future__ import annotations

import os
from typing import Any

import jwt
from fastapi import HTTPException, Request

MAX_BODY_BYTES = 1_048_576


async def authenticated_payload(request: Request, *, audience: str) -> dict[str, Any]:
    """Return a bounded JSON object after token, header, and payload binding checks."""
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > MAX_BODY_BYTES:
                raise HTTPException(413, "request too large")
        except ValueError as exc:
            raise HTTPException(400, "invalid content length") from exc
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "service authentication required")
    secret = os.environ.get("LEDGERAI_SERVICE_TOKEN_SECRET", "")
    if len(secret.encode()) < 32:
        raise HTTPException(503, "service authentication unavailable")
    try:
        claims = jwt.decode(
            authorization[7:],
            secret,
            algorithms=["HS256"],
            audience=audience,
            issuer=os.environ.get("LEDGERAI_SERVICE_TOKEN_ISSUER", "ledgerai-backend"),
            options={
                "require": ["exp", "iat", "iss", "aud", "sub", "tenant_id", "operation_id"]
            },
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, "service authentication failed") from exc
    try:
        payload = await request.json()
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(422, "valid JSON object required") from exc
    if not isinstance(payload, dict):
        raise HTTPException(422, "object payload required")
    context = payload.get("tenant_context")
    if not isinstance(context, dict):
        raise HTTPException(422, "tenant context required")
    header_bindings = {
        "tenant_id": "x-tenant-id",
        "organization_id": "x-organization-id",
        "legal_entity_id": "x-legal-entity-id",
    }
    for field, header in header_bindings.items():
        value = request.headers.get(header)
        if not value or context.get(field) != value:
            raise HTTPException(403, "authenticated tenant context mismatch")
    operation_id = request.headers.get("x-operation-id")
    correlation_id = request.headers.get("x-correlation-id")
    if not operation_id or not correlation_id:
        raise HTTPException(400, "operation and correlation headers required")
    if claims.get("tenant_id") != context["tenant_id"]:
        raise HTTPException(403, "authenticated tenant context mismatch")
    if claims.get("operation_id") != operation_id:
        raise HTTPException(403, "authenticated operation mismatch")
    payload_operation = payload.get("operation_id")
    if payload_operation is not None and str(payload_operation) != operation_id:
        raise HTTPException(403, "payload operation mismatch")
    correlation = payload.get("correlation")
    if isinstance(correlation, dict) and correlation.get("correlation_id") != correlation_id:
        raise HTTPException(403, "payload correlation mismatch")
    return payload
