from __future__ import annotations

import asyncio
from datetime import date
from time import time
from typing import Any

import httpx
import jwt
import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from test_role3_reconciliation import TENANT, identifier, invoice, request, transaction

from ledgerai_backend.integration.adapters import (
    AdapterError,
    AdapterSecurity,
    ReconciliationResult,
    Role3Adapter,
    SignedServiceTokenProvider,
)
from ledgerai_backend.reconciliation.api import create_reconciliation_app
from ledgerai_backend.reconciliation.engine import ReconciliationEngine
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


def make_role3_adapter(app: FastAPI, *, audience: str = "ledgerai-role3") -> Role3Adapter:
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://role3.test",
    )
    token_provider = SignedServiceTokenProvider(
        issuer="ledgerai-backend",
        subject="service:backend",
        secret=SECRET,
    )
    security = AdapterSecurity(
        base_url="http://role3.test",
        audience=audience,
        environment="test",
        maximum_attempts=1,
    )
    return Role3Adapter(security, token_provider, client=client)


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
    "bad_audience",
    [
        "ledgerai:role3",
        "role3",
        "role1",
        "role2",
        "ledgerai-role6",
        None,
    ],
)
async def test_audience_isolation_rejects_invalid_single_audiences(
    bad_audience: str | None,
) -> None:
    app = create_reconciliation_app(Role3Security(secret=SECRET))
    now = int(time())
    claims: dict[str, Any] = {
        "iss": "ledgerai-backend",
        "sub": "ledgerai-backend",
        "iat": now,
        "exp": now + 60,
        "tenant_id": str(TENANT.tenant_id),
        "operation_id": str(identifier("api-operation")),
    }
    if bad_audience is not None:
        claims["aud"] = bad_audience
    bad_token = jwt.encode(claims, SECRET, algorithm="HS256")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://role3.test"
    ) as client:
        response = await client.post(
            "/v1/reconciliations", json=payload(), headers=headers(bad_token)
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_audience_isolation_rejects_multiple_invalid_audiences() -> None:
    app = create_reconciliation_app(Role3Security(secret=SECRET))
    now = int(time())
    claims: dict[str, Any] = {
        "iss": "ledgerai-backend",
        "sub": "ledgerai-backend",
        "aud": ["role1", "role2", "ledgerai:role3"],
        "iat": now,
        "exp": now + 60,
        "tenant_id": str(TENANT.tenant_id),
        "operation_id": str(identifier("api-operation")),
    }
    bad_token = jwt.encode(claims, SECRET, algorithm="HS256")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://role3.test"
    ) as client:
        response = await client.post(
            "/v1/reconciliations", json=payload(), headers=headers(bad_token)
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_service_authentication_token_and_foreign_tenant_rejected() -> None:
    app = create_reconciliation_app(Role3Security(secret=SECRET))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://role3.test"
    ) as client:
        invalid_resp = await client.post(
            "/v1/reconciliations", json=payload(), headers=headers("invalid-token")
        )
        assert invalid_resp.status_code == 401

        foreign_token = token(tenant_id=str(identifier("foreign-tenant")))
        foreign_resp = await client.post(
            "/v1/reconciliations", json=payload(), headers=headers(foreign_token)
        )
        assert foreign_resp.status_code == 401


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


# =========================================================================
# Canonical Role 4 Role3Adapter Compatibility Tests
# =========================================================================


@pytest.mark.asyncio
async def test_role4_adapter_compatibility_happy_path() -> None:
    app = create_reconciliation_app(Role3Security(secret=SECRET))
    adapter = make_role3_adapter(app)
    req = request([invoice("adapter-test")], [transaction("adapter-test")], operation="role4-op")
    op_id = req.operation_id
    corr_id = req.correlation_id

    result = await adapter.request_reconciliation(
        payload=req.model_dump(mode="json"),
        tenant_context=TENANT,
        operation_id=op_id,
        correlation_id=corr_id,
    )
    assert isinstance(result, ReconciliationResult)
    assert result.schema_version == "1.0"
    assert result.tenant_context == TENANT
    assert result.proposal.match_type == "ONE_TO_ONE"
    assert result.proposal.status == "PROPOSED"
    assert result.proposal.correlation.request_id == op_id
    assert result.proposal.producer.algorithm_version == "reconciliation-deterministic/1.0.0"
    assert result.proposal.producer.rule_or_policy_version == "reconciliation-rules/1.0.0"


@pytest.mark.asyncio
async def test_role4_adapter_planted_fifty_rupee_mismatch_preserved() -> None:
    app = create_reconciliation_app(Role3Security(secret=SECRET))
    adapter = make_role3_adapter(app)
    req = request(
        [invoice("nova", "1250.00", reference="NOVA-DEMO-PAY-001")],
        [
            transaction("nova-payment", "1250.00", reference="NOVA-DEMO-PAY-001"),
            transaction(
                "nova-planted",
                "50.00",
                reference="NOVA-DEMO-ISSUE-001",
                party="SYNTHETIC REVIEW VENDOR",
                booking_date=date(2026, 9, 16),
            ),
        ],
        operation="nova-operation",
    )
    result = await adapter.request_reconciliation(
        payload=req.model_dump(mode="json"),
        tenant_context=TENANT,
        operation_id=req.operation_id,
        correlation_id=req.correlation_id,
    )
    assert isinstance(result, ReconciliationResult)
    assert result.proposal.match_type == "ONE_TO_ONE"
    assert result.proposal.status == "REVIEW_REQUIRED"
    mismatch = [e for e in result.exceptions if e.exception_type == "AMOUNT_MISMATCH"]
    assert len(mismatch) == 1
    assert "BATCH_AMOUNT_MISMATCH" in mismatch[0].reason_codes
    assert "50.00" in mismatch[0].explanation
    assert mismatch[0].severity == "HIGH"
    assert mismatch[0].detector.algorithm_version == "reconciliation-deterministic/1.0.0"
    assert mismatch[0].detector.rule_or_policy_version == "reconciliation-rules/1.0.0"


@pytest.mark.asyncio
async def test_role4_adapter_wrong_tenant_response_rejected() -> None:
    foreign_tenant = TENANT.model_copy(update={"tenant_id": identifier("foreign-tenant")})
    canon_resp = ReconciliationEngine().reconcile(request([invoice("test")], [transaction("test")]))
    bad_resp_data = canon_resp.model_dump(mode="json")
    bad_resp_data["tenant_context"] = foreign_tenant.model_dump(mode="json")

    def wrong_tenant_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=bad_resp_data, headers={"content-type": "application/json"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(wrong_tenant_handler))
    token_provider = SignedServiceTokenProvider(
        issuer="ledgerai-backend", subject="service:backend", secret=SECRET
    )
    security = AdapterSecurity(
        base_url="http://role3.test",
        audience="ledgerai-role3",
        environment="test",
        maximum_attempts=1,
    )
    adapter = Role3Adapter(security, token_provider, client=client)

    with pytest.raises(AdapterError, match="TENANT_CONTEXT_MISMATCH"):
        await adapter.request_reconciliation(
            payload={},
            tenant_context=TENANT,
            operation_id=identifier("op"),
            correlation_id=identifier("corr"),
        )


@pytest.mark.asyncio
async def test_role4_adapter_malformed_response_rejected() -> None:
    def malformed_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"unexpected": "structure"},
            headers={"content-type": "application/json"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(malformed_handler))
    token_provider = SignedServiceTokenProvider(
        issuer="ledgerai-backend", subject="service:backend", secret=SECRET
    )
    security = AdapterSecurity(
        base_url="http://role3.test",
        audience="ledgerai-role3",
        environment="test",
        maximum_attempts=1,
    )
    adapter = Role3Adapter(security, token_provider, client=client)

    with pytest.raises(AdapterError, match="CONTRACT_REJECTED"):
        await adapter.request_reconciliation(
            payload={},
            tenant_context=TENANT,
            operation_id=identifier("op"),
            correlation_id=identifier("corr"),
        )


def test_unknown_fields_in_response_forbidden_by_contract() -> None:
    valid_data = payload()
    valid_data["extra_forbidden_field"] = "bad"
    with pytest.raises(ValidationError):
        ReconciliationResult.model_validate(valid_data)
