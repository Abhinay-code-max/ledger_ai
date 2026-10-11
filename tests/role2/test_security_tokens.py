"""Tests for service security, token audience/tenant binding, and limits."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import httpx
import jwt
import pytest

from ledgerai_role2.api.app import create_role2_app
from ledgerai_role2.config import Role2Settings

SECRET = "a" * 32
ISSUER = "ledgerai-backend"
AUDIENCE = "role2"
TENANT = UUID("10000000-0000-4000-8000-000000000001")
ORG = UUID("10000000-0000-4000-8000-000000000002")
ENTITY = UUID("10000000-0000-4000-8000-000000000003")


def make_token(
    *,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    tenant_id: UUID = TENANT,
    operation_id: UUID,
    ttl: int = 60,
    secret: str = SECRET,
) -> str:
    now = int(time.time())
    payload = {
        "iss": issuer,
        "sub": "service:backend",
        "aud": audience,
        "iat": now,
        "exp": now + ttl,
        "tenant_id": str(tenant_id),
        "operation_id": str(operation_id),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def headers(
    token: str,
    operation_id: UUID,
    tenant_id: UUID = TENANT,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(tenant_id),
        "X-Organization-ID": str(ORG),
        "X-Legal-Entity-ID": str(ENTITY),
        "X-Operation-ID": str(operation_id),
        "X-Correlation-ID": str(uuid4()),
    }


@pytest.fixture
def app():
    settings = Role2Settings(
        service_token_secret=SECRET,  # type: ignore[arg-type]
        service_token_audience=AUDIENCE,
        service_token_issuer=ISSUER,
        max_request_bytes=1000,  # small for testing size limit
    )
    return create_role2_app(settings)


@pytest.mark.asyncio
async def test_valid_token_allows_request(app) -> None:
    op_id = uuid4()
    token = make_token(operation_id=op_id)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/journal-posting-status",
            headers=headers(token, op_id),
            json={"operation_id": str(op_id)},
        )
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_missing_token_returns_401(app) -> None:
    op_id = uuid4()
    h = headers("dummy", op_id)
    del h["Authorization"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/journal-posting-status",
            headers=h,
            json={"operation_id": str(op_id)},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_returns_401(app) -> None:
    op_id = uuid4()
    token = make_token(operation_id=op_id, ttl=-10)  # already expired!
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/journal-posting-status",
            headers=headers(token, op_id),
            json={"operation_id": str(op_id)},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_wrong_audience_returns_401(app) -> None:
    op_id = uuid4()
    token = make_token(operation_id=op_id, audience="role3-reconciliation")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/journal-posting-status",
            headers=headers(token, op_id),
            json={"operation_id": str(op_id)},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "INVALID_AUDIENCE"


@pytest.mark.asyncio
async def test_wrong_issuer_returns_401(app) -> None:
    op_id = uuid4()
    token = make_token(operation_id=op_id, issuer="untrusted-attacker")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/journal-posting-status",
            headers=headers(token, op_id),
            json={"operation_id": str(op_id)},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "INVALID_ISSUER"


@pytest.mark.asyncio
async def test_wrong_secret_signature_returns_401(app) -> None:
    op_id = uuid4()
    token = make_token(operation_id=op_id, secret="b" * 32)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/journal-posting-status",
            headers=headers(token, op_id),
            json={"operation_id": str(op_id)},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tenant_binding_mismatch_returns_403(app) -> None:
    op_id = uuid4()
    # Token has TENANT, but request header has foreign tenant!
    token = make_token(operation_id=op_id, tenant_id=TENANT)
    foreign_tenant = uuid4()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/journal-posting-status",
            headers=headers(token, op_id, tenant_id=foreign_tenant),
            json={"operation_id": str(op_id)},
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "TENANT_MISMATCH"


@pytest.mark.asyncio
async def test_operation_binding_mismatch_returns_403(app) -> None:
    token_op_id = uuid4()
    header_op_id = uuid4()  # Mismatch!
    token = make_token(operation_id=token_op_id)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/journal-posting-status",
            headers=headers(token, header_op_id),
            json={"operation_id": str(header_op_id)},
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "OPERATION_MISMATCH"


@pytest.mark.asyncio
async def test_oversized_payload_returns_413(app) -> None:
    op_id = uuid4()
    token = make_token(operation_id=op_id)
    huge_payload = {"op": str(op_id), "padding": "x" * 2000}  # Limit is 1000 bytes
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/journal-posting-status",
            headers=headers(token, op_id),
            json=huge_payload,
        )
        assert resp.status_code == 413
        assert resp.json()["code"] == "REQUEST_TOO_LARGE"
