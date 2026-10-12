from __future__ import annotations

from collections.abc import Callable
from time import time
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ledgerai_backend.demo.comparator import compare, normalize
from ledgerai_backend.demo.role1 import create_demo_role1_app
from ledgerai_backend.demo.role2 import create_demo_role2_app
from ledgerai_backend.demo.role3 import create_demo_role3_app
from ledgerai_backend.demo.role6 import create_demo_role6_app
from ledgerai_backend.integration.adapters import ReconciliationResult, Role6Classification
from ledgerai_contracts.v1.accounting import AccountingValidationResult
from ledgerai_contracts.v1.documents import DocumentExtraction

SECRET = "synthetic-service-secret-for-boundary-tests"
TENANT = UUID("11111111-1111-4111-8111-111111111111")
ORGANIZATION = UUID("22222222-2222-4222-8222-222222222222")
ENTITY = UUID("33333333-3333-4333-8333-333333333333")


def _headers(audience: str, operation_id: UUID, *, tenant_id: UUID = TENANT) -> dict[str, str]:
    now = int(time())
    token = jwt.encode(
        {
            "iss": "ledgerai-backend",
            "sub": "ledgerai-backend",
            "aud": audience,
            "iat": now,
            "exp": now + 300,
            "tenant_id": str(tenant_id),
            "operation_id": str(operation_id),
        },
        SECRET,
        algorithm="HS256",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT),
        "X-Organization-ID": str(ORGANIZATION),
        "X-Legal-Entity-ID": str(ENTITY),
        "X-Operation-ID": str(operation_id),
        "X-Correlation-ID": str(operation_id),
    }


def _payload(operation_id: UUID) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "operation_id": str(operation_id),
        "tenant_context": {
            "tenant_id": str(TENANT),
            "organization_id": str(ORGANIZATION),
            "legal_entity_id": str(ENTITY),
        },
    }


@pytest.fixture(autouse=True)
def service_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERAI_SERVICE_TOKEN_SECRET", SECRET)
    monkeypatch.setenv("LEDGERAI_SERVICE_TOKEN_ISSUER", "ledgerai-backend")


def _post(app: FastAPI, path: str, audience: str, payload: dict[str, object]) -> object:
    operation_id = UUID(str(payload["operation_id"]))
    with TestClient(app) as client:
        response = client.post(path, headers=_headers(audience, operation_id), json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_role1_boundary_returns_canonical_extraction() -> None:
    operation_id = uuid4()
    payload = _payload(operation_id)
    payload.update({"document_id": str(uuid4()), "document_version_id": str(uuid4())})
    result = _post(create_demo_role1_app(), "/v1/extractions", "ledgerai-role1", payload)
    DocumentExtraction.model_validate(result)


def test_role2_boundary_returns_canonical_validation() -> None:
    operation_id = uuid4()
    payload = _payload(operation_id)
    payload.update(
        {
            "proposal": {
                "resource_type": "journal_proposal",
                "resource_id": str(uuid4()),
                "resource_version": "1",
            },
            "proposal_version": "1",
        }
    )
    result = _post(create_demo_role2_app(), "/v1/accounting-validations", "ledgerai-role2", payload)
    AccountingValidationResult.model_validate(result)


def test_role3_boundary_returns_canonical_reconciliation() -> None:
    operation_id = uuid4()
    payload = _payload(operation_id)
    payload["transaction_ids"] = [str(uuid4()), str(uuid4())]
    result = _post(create_demo_role3_app(), "/v1/reconciliations", "ledgerai-role3", payload)
    ReconciliationResult.model_validate(result)


def test_role6_boundary_returns_strict_classification() -> None:
    operation_id = uuid4()
    payload = _payload(operation_id)
    payload["resource_id"] = str(uuid4())
    result = _post(create_demo_role6_app(), "/v1/classifications", "ledgerai-role6", payload)
    Role6Classification.model_validate(result)


@pytest.mark.parametrize(
    ("factory", "path", "audience"),
    [
        (create_demo_role1_app, "/v1/extractions", "ledgerai-role1"),
        (create_demo_role2_app, "/v1/accounting-validations", "ledgerai-role2"),
        (create_demo_role3_app, "/v1/reconciliations", "ledgerai-role3"),
        (create_demo_role6_app, "/v1/classifications", "ledgerai-role6"),
    ],
)
def test_every_stub_rejects_wrong_operation_binding(
    factory: Callable[[], FastAPI],
    path: str,
    audience: str,
) -> None:
    payload = _payload(uuid4())
    with TestClient(factory()) as client:
        response = client.post(path, headers=_headers(audience, uuid4()), json=payload)
    assert response.status_code == 403


def test_stub_rejects_cross_tenant_token() -> None:
    operation_id = uuid4()
    payload = _payload(operation_id)
    payload.update({"document_id": str(uuid4()), "document_version_id": str(uuid4())})
    with TestClient(create_demo_role1_app()) as client:
        response = client.post(
            "/v1/extractions",
            headers=_headers("ledgerai-role1", operation_id, tenant_id=uuid4()),
            json=payload,
        )
    assert response.status_code == 403


def test_stub_rejects_oversized_declared_request() -> None:
    operation_id = uuid4()
    headers = _headers("ledgerai-role6", operation_id)
    headers["Content-Length"] = "1048577"
    with TestClient(create_demo_role6_app()) as client:
        response = client.post("/v1/classifications", headers=headers, content=b"{}")
    assert response.status_code == 413


def test_result_comparator_removes_only_known_volatile_metadata() -> None:
    left = {
        "scenario": "nova-phase4-v1",
        "correlation_id": str(uuid4()),
        "audit_actions": ["B", "A"],
        "amount": "1250.00",
    }
    right = {
        "scenario": "nova-phase4-v1",
        "correlation_id": str(uuid4()),
        "audit_actions": ["A", "B"],
        "amount": "1250.00",
    }
    assert compare(left, right)
    assert normalize(left)["amount"] == "1250.00"
    assert not compare(left, {**right, "amount": "1250.01"})
