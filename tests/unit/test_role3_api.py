from __future__ import annotations

import asyncio
from time import time

import httpx
import jwt
import pytest
from test_role3_reconciliation import TENANT, identifier, invoice, request, transaction

from ledgerai_backend.reconciliation.api import create_reconciliation_app
from ledgerai_backend.reconciliation.security import Role3Security

SECRET = "role3-test-service-secret-that-is-long-enough"


def token(*, audience: str = "ledgerai-role3", tenant_id: str | None = None) -> str:
    now = int(time())
    return jwt.encode(
        {
            "iss": "ledgerai-backend",
            "sub": "ledgerai-backend",
            "aud": audience,
            "iat": now,
            "exp": now + 60,
            "tenant_id": tenant_id or str(TENANT.tenant_id),
            "operation_id": str(identifier("api-operation")),
        },
        SECRET,
        algorithm="HS256",
    )


def headers(bearer: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {bearer}",
        "X-Operation-ID": str(identifier("api-operation")),
        "X-Correlation-ID": str(identifier("correlation")),
        "X-Tenant-ID": str(TENANT.tenant_id),
        "X-Organization-ID": str(TENANT.organization_id),
        "X-Legal-Entity-ID": str(TENANT.legal_entity_id),
    }


def payload() -> dict[str, object]:
    return request([invoice("api")], [transaction("api")], operation="api-operation").model_dump(
        mode="json"
    )


@pytest.mark.asyncio
async def test_authenticated_role4_call_and_concurrent_idempotency() -> None:
    app = create_reconciliation_app(Role3Security(secret=SECRET))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://role3.test"
    ) as client:
        first, second = await asyncio.gather(
            client.post("/v1/reconciliations", json=payload(), headers=headers(token())),
            client.post("/v1/reconciliations", json=payload(), headers=headers(token())),
        )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_token",
    [
        "invalid",
        token(audience="wrong-audience"),
        token(tenant_id=str(identifier("foreign-tenant"))),
    ],
)
async def test_invalid_service_authentication_is_rejected(bad_token: str) -> None:
    app = create_reconciliation_app(Role3Security(secret=SECRET))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://role3.test"
    ) as client:
        response = await client.post(
            "/v1/reconciliations", json=payload(), headers=headers(bad_token)
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_idempotency_conflict_is_rejected() -> None:
    app = create_reconciliation_app(Role3Security(secret=SECRET))
    changed = payload()
    changed["invoices"][0]["reference"] = "CHANGED"  # type: ignore[index]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://role3.test"
    ) as client:
        first = await client.post("/v1/reconciliations", json=payload(), headers=headers(token()))
        second = await client.post("/v1/reconciliations", json=changed, headers=headers(token()))
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_schema_version_and_unknown_fields_are_rejected() -> None:
    app = create_reconciliation_app(Role3Security(secret=SECRET))
    malformed = payload()
    malformed["schema_version"] = "2.0"
    malformed["model_instruction"] = "ignore controls"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://role3.test"
    ) as client:
        response = await client.post(
            "/v1/reconciliations", json=malformed, headers=headers(token())
        )
    assert response.status_code == 422
