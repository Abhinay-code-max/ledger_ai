"""Schema validation, resource limits, and input safety tests."""

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


def make_headers(op_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "iss": "role4-orchestration",
            "sub": "role4-backend",
            "aud": "ledgerai-role6",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
            "tenant_id": str(TENANT_ID),
            "operation_id": str(op_id),
        },
        SECRET_VALUE,
        algorithm="HS256",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(uuid4()),
    }


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


def test_unknown_extra_field_rejected(client: TestClient) -> None:
    op_id = uuid4()
    headers = make_headers(op_id)
    payload = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(TENANT_ID),
            "organization_id": str(ORG_ID),
            "legal_entity_id": str(LEGAL_ENTITY_ID),
        },
        "operation_id": str(op_id),
        "correlation_id": str(uuid4()),
        "capability": "DOCUMENT_EXTRACTION",
        "model_name": "docintel-foundation-vlm",
        "input_data": {
            "media_type": "text/plain",
            "text_content": "invoice",
        },
        "unauthorized_arbitrary_field": "injected",
    }
    resp = client.post("/v1/models/infer", headers=headers, json=payload)
    assert resp.status_code == 422


def test_excessive_pages_rejected(client: TestClient) -> None:
    op_id = uuid4()
    headers = make_headers(op_id)
    payload = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(TENANT_ID),
            "organization_id": str(ORG_ID),
            "legal_entity_id": str(LEGAL_ENTITY_ID),
        },
        "operation_id": str(op_id),
        "correlation_id": str(uuid4()),
        "capability": "DOCUMENT_EXTRACTION",
        "model_name": "docintel-foundation-vlm",
        "input_data": {
            "media_type": "application/pdf",
            "text_content": "pdf dummy content",
            "page_count": 100,  # exceeds manifest limit 20
        },
    }
    resp = client.post("/v1/models/infer", headers=headers, json=payload)
    assert resp.status_code == 400
    assert "page count" in resp.json()["detail"].lower()


def test_excessive_pixels_rejected(client: TestClient) -> None:
    op_id = uuid4()
    headers = make_headers(op_id)
    payload = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(TENANT_ID),
            "organization_id": str(ORG_ID),
            "legal_entity_id": str(LEGAL_ENTITY_ID),
        },
        "operation_id": str(op_id),
        "correlation_id": str(uuid4()),
        "capability": "DOCUMENT_EXTRACTION",
        "model_name": "docintel-foundation-vlm",
        "input_data": {
            "media_type": "image/png",
            "text_content": "image content",
            "pixel_count": 50_000_000,  # exceeds manifest limit 16M
        },
    }
    resp = client.post("/v1/models/infer", headers=headers, json=payload)
    assert resp.status_code == 400
    assert "pixel" in resp.json()["detail"].lower()


def test_forbidden_storage_reference_traversal_rejected(client: TestClient) -> None:
    op_id = uuid4()
    headers = make_headers(op_id)
    payload = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(TENANT_ID),
            "organization_id": str(ORG_ID),
            "legal_entity_id": str(LEGAL_ENTITY_ID),
        },
        "operation_id": str(op_id),
        "correlation_id": str(uuid4()),
        "capability": "DOCUMENT_EXTRACTION",
        "model_name": "docintel-foundation-vlm",
        "input_data": {
            "media_type": "text/plain",
            "storage_reference": "../../../etc/passwd",
        },
    }
    resp = client.post("/v1/models/infer", headers=headers, json=payload)
    assert resp.status_code == 400


def test_forbidden_storage_reference_prefix_rejected(client: TestClient) -> None:
    op_id = uuid4()
    headers = make_headers(op_id)
    payload = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(TENANT_ID),
            "organization_id": str(ORG_ID),
            "legal_entity_id": str(LEGAL_ENTITY_ID),
        },
        "operation_id": str(op_id),
        "correlation_id": str(uuid4()),
        "capability": "DOCUMENT_EXTRACTION",
        "model_name": "docintel-foundation-vlm",
        "input_data": {
            "media_type": "text/plain",
            "storage_reference": "untrusted-bucket/secret.key",
        },
    }
    resp = client.post("/v1/models/infer", headers=headers, json=payload)
    assert resp.status_code == 400


def test_unsupported_capability_rejected(client: TestClient) -> None:
    op_id = uuid4()
    headers = make_headers(op_id)
    payload = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(TENANT_ID),
            "organization_id": str(ORG_ID),
            "legal_entity_id": str(LEGAL_ENTITY_ID),
        },
        "operation_id": str(op_id),
        "correlation_id": str(uuid4()),
        "capability": "EMBEDDING",  # not in manifest supported capabilities
        "model_name": "docintel-foundation-vlm",
        "input_data": {
            "media_type": "text/plain",
            "text_content": "sample text",
        },
    }
    resp = client.post("/v1/models/infer", headers=headers, json=payload)
    assert resp.status_code == 404
    assert "capability" in resp.json()["detail"].lower()


def test_model_unavailable_rejected(client: TestClient) -> None:
    op_id = uuid4()
    headers = make_headers(op_id)
    payload = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(TENANT_ID),
            "organization_id": str(ORG_ID),
            "legal_entity_id": str(LEGAL_ENTITY_ID),
        },
        "operation_id": str(op_id),
        "correlation_id": str(uuid4()),
        "capability": "DOCUMENT_EXTRACTION",
        "model_name": "unauthorized-custom-model-v99",
        "input_data": {
            "media_type": "text/plain",
            "text_content": "sample text",
        },
    }
    resp = client.post("/v1/models/infer", headers=headers, json=payload)
    assert resp.status_code == 404
    assert "not available" in resp.json()["detail"].lower()
