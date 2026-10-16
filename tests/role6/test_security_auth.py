"""Authentication and tenant isolation tests for Role 6 runtime."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ledgerai_role6.app import create_role6_app
from ledgerai_role6.config import Role6Settings

SECRET_VALUE = "a" * 32
SECRET = SecretStr(SECRET_VALUE)
TENANT_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("10000000-0000-0000-0000-000000000002")
LEGAL_ENTITY_ID = UUID("10000000-0000-0000-0000-000000000003")


def make_service_token(
    *,
    secret: str = SECRET_VALUE,
    issuer: str = "role4-orchestration",
    subject: str = "role4-backend",
    audience: str = "ledgerai-role6",
    tenant_id: UUID = TENANT_ID,
    operation_id: UUID | None = None,
    ttl: int = 60,
    expired: bool = False,
    nbf_future: bool = False,
) -> str:
    now = int(time.time())
    iat = now - 100 if expired else now
    exp = now - 10 if expired else now + ttl
    payload = {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "iat": iat,
        "exp": exp,
        "tenant_id": str(tenant_id),
        "operation_id": str(operation_id or uuid4()),
    }
    if nbf_future:
        payload["nbf"] = now + 100
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def client() -> TestClient:
    settings = Role6Settings(
        environment="test",
        service_token_secret=SECRET,
        service_audience="ledgerai-role6",
        active_backend="deterministic",
    )
    app = create_role6_app(settings)
    return TestClient(app)


def test_valid_service_request(client: TestClient) -> None:
    op_id = uuid4()
    corr_id = uuid4()
    token = make_service_token(operation_id=op_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(corr_id),
    }
    payload = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(TENANT_ID),
            "organization_id": str(ORG_ID),
            "legal_entity_id": str(LEGAL_ENTITY_ID),
        },
        "operation_id": str(op_id),
        "correlation_id": str(corr_id),
        "capability": "DOCUMENT_EXTRACTION",
        "model_name": "docintel-foundation-vlm",
        "input_data": {
            "media_type": "text/plain",
            "text_content": "INVOICE NUMBER: 12345\nTOTAL AMOUNT: USD 500.00\n",
        },
    }
    resp = client.post("/v1/models/infer", headers=headers, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["schema_version"] == "1.0"
    assert data["execution_metadata"]["backend_type"] == "DETERMINISTIC"
    assert len(data["output"]["fields"]) >= 2


def test_invalid_signature_rejected(client: TestClient) -> None:
    op_id = uuid4()
    token = make_service_token(secret="b" * 32, operation_id=op_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(uuid4()),
    }
    resp = client.post("/v1/models/infer", headers=headers, json={})
    assert resp.status_code == 401


def test_wrong_issuer_rejected(client: TestClient) -> None:
    op_id = uuid4()
    token = make_service_token(issuer="unknown-untrusted-issuer", operation_id=op_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(uuid4()),
    }
    resp = client.post("/v1/models/infer", headers=headers, json={})
    assert resp.status_code == 403


def test_wrong_audience_rejected(client: TestClient) -> None:
    op_id = uuid4()
    token = make_service_token(audience="ledgerai-role2", operation_id=op_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(uuid4()),
    }
    resp = client.post("/v1/models/infer", headers=headers, json={})
    assert resp.status_code == 403


def test_expired_token_rejected(client: TestClient) -> None:
    op_id = uuid4()
    token = make_service_token(operation_id=op_id, expired=True)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(uuid4()),
    }
    resp = client.post("/v1/models/infer", headers=headers, json={})
    assert resp.status_code == 401


def test_not_yet_valid_token_rejected(client: TestClient) -> None:
    op_id = uuid4()
    token = make_service_token(operation_id=op_id, nbf_future=True)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(uuid4()),
    }
    resp = client.post("/v1/models/infer", headers=headers, json={})
    assert resp.status_code == 401


def test_tenant_mismatch_rejected(client: TestClient) -> None:
    op_id = uuid4()
    token = make_service_token(tenant_id=TENANT_ID, operation_id=op_id)
    different_tenant = uuid4()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(different_tenant),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(uuid4()),
    }
    resp = client.post("/v1/models/infer", headers=headers, json={})
    assert resp.status_code == 403


def test_unauthorized_calling_service_rejected(client: TestClient) -> None:
    op_id = uuid4()
    token = make_service_token(subject="evil-attacker-service", operation_id=op_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(uuid4()),
    }
    resp = client.post("/v1/models/infer", headers=headers, json={})
    assert resp.status_code == 403


def test_payload_tenant_mismatch_rejected(client: TestClient) -> None:
    op_id = uuid4()
    corr_id = uuid4()
    token = make_service_token(operation_id=op_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(corr_id),
    }
    different_tenant = uuid4()
    payload = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(different_tenant),
            "organization_id": str(ORG_ID),
            "legal_entity_id": str(LEGAL_ENTITY_ID),
        },
        "operation_id": str(op_id),
        "correlation_id": str(corr_id),
        "capability": "DOCUMENT_EXTRACTION",
        "model_name": "docintel-foundation-vlm",
        "input_data": {
            "media_type": "text/plain",
            "text_content": "test invoice",
        },
    }
    resp = client.post("/v1/models/infer", headers=headers, json=payload)
    assert resp.status_code == 403


def test_missing_token_rejected(client: TestClient) -> None:
    headers = {
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(uuid4()),
        "X-Correlation-ID": str(uuid4()),
    }
    resp = client.post("/v1/models/infer", headers=headers, json={})
    assert resp.status_code == 401


def test_wrong_operation_rejected(client: TestClient) -> None:
    op_id = uuid4()
    other_op_id = uuid4()
    corr_id = uuid4()
    token = make_service_token(operation_id=op_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(corr_id),
    }
    payload = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(TENANT_ID),
            "organization_id": str(ORG_ID),
            "legal_entity_id": str(LEGAL_ENTITY_ID),
        },
        "operation_id": str(other_op_id),
        "correlation_id": str(corr_id),
        "capability": "DOCUMENT_EXTRACTION",
        "model_name": "docintel-foundation-vlm",
        "input_data": {
            "media_type": "text/plain",
            "text_content": "test invoice",
        },
    }
    resp = client.post("/v1/models/infer", headers=headers, json=payload)
    assert resp.status_code == 403


def test_forged_token_rejected(client: TestClient) -> None:
    op_id = uuid4()
    headers = {
        "Authorization": "Bearer forged.invalid.token.structure",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(uuid4()),
    }
    resp = client.post("/v1/models/infer", headers=headers, json={})
    assert resp.status_code == 401
