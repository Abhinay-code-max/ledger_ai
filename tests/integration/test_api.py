from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from phase1_postgres_support import (
    ACME_ENTITY,
    ACME_ORGANIZATION,
    NO_PERMISSION_MEMBERSHIP,
    admin_dsn,
    runtime_dsn,
)
from pydantic import SecretStr

from ledgerai_backend.core.config import Settings
from ledgerai_backend.core.identity import DeterministicTestIdentityProvider, VerifiedIdentity
from ledgerai_backend.database.seed import stable_id
from ledgerai_backend.main import create_app

pytestmark = pytest.mark.postgres

ISSUER = "https://identity.demo.invalid/"


@pytest.fixture
def api() -> Iterator[TestClient]:
    settings = Settings(
        environment="test",
        allowed_hosts=["testserver"],
        database_dsn=SecretStr(runtime_dsn().replace("postgresql://", "postgresql+psycopg://", 1)),
    )
    identity = DeterministicTestIdentityProvider(
        {
            "nova-admin-token": VerifiedIdentity(ISSUER, "nova-admin"),
            "nova-viewer-token": VerifiedIdentity(ISSUER, "nova-viewer"),
            "no-permission-token": VerifiedIdentity(ISSUER, "nova-no-permission"),
            "acme-admin-token": VerifiedIdentity(ISSUER, "acme-admin"),
        }
    )
    with TestClient(create_app(settings, identity_provider=identity)) as client:
        yield client


def headers(token: str = "nova-admin-token", workspace: str = "nova") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Workspace-Code": workspace}


def test_valid_authentication_and_me(api: TestClient) -> None:
    response = api.get("/api/v1/me", headers=headers())
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == str(stable_id("nova:tenant"))
    assert "tenant-administrator" in body["roles"]
    assert "workspace:read" in body["permissions"]


@pytest.mark.parametrize("authorization", [None, "Bearer malformed", "Basic synthetic"])
def test_missing_or_malformed_authentication_is_safe(
    api: TestClient, authorization: str | None
) -> None:
    request_headers = {"X-Workspace-Code": "nova"}
    if authorization:
        request_headers["Authorization"] = authorization
    response = api.get("/api/v1/me", headers=request_headers)
    assert response.status_code == 401
    assert response.json()["category"] == "AUTHENTICATION"
    assert "malformed" not in response.text


def test_insufficient_permission(api: TestClient) -> None:
    response = api.get("/api/v1/organizations", headers=headers("no-permission-token"))
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_foreign_ids_are_neutral_not_found(api: TestClient) -> None:
    organization = api.get(f"/api/v1/organizations/{ACME_ORGANIZATION}", headers=headers())
    entity = api.get(f"/api/v1/legal-entities/{ACME_ENTITY}", headers=headers())
    for response in (organization, entity):
        assert response.status_code == 404
        assert response.json()["code"] == "RESOURCE_NOT_FOUND"
        assert "tenant" not in response.json()["message"].lower()


def test_lists_and_pagination_remain_tenant_isolated(api: TestClient) -> None:
    organizations = api.get(
        "/api/v1/organizations?limit=1&offset=0&tenant_id=" + str(uuid4()),
        headers=headers(),
    )
    entities = api.get("/api/v1/legal-entities?limit=1&offset=0", headers=headers())
    assert organizations.status_code == 200
    assert entities.status_code == 200
    assert [item["code"] for item in organizations.json()["items"]] == ["nova-india"]
    assert [item["code"] for item in entities.json()["items"]] == ["nova-technologies-in"]


def test_request_body_tenant_id_cannot_override_verified_scope(api: TestClient) -> None:
    response = api.request(
        "GET",
        "/api/v1/organizations",
        headers=headers(),
        json={"tenant_id": str(uuid4())},
    )
    assert response.status_code == 200
    assert [item["code"] for item in response.json()["items"]] == ["nova-india"]


def test_foreign_scope_selector_is_denied_without_disclosure(api: TestClient) -> None:
    scoped_headers = headers()
    scoped_headers["X-Organization-ID"] = str(ACME_ORGANIZATION)
    response = api.get("/api/v1/me", headers=scoped_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "WORKSPACE_ACCESS_DENIED"


def test_suspended_membership_cannot_authorize(api: TestClient) -> None:
    with psycopg.connect(admin_dsn()) as connection:
        connection.execute(
            "UPDATE memberships SET status='SUSPENDED' WHERE id=%s",
            (NO_PERMISSION_MEMBERSHIP,),
        )
    try:
        response = api.get("/api/v1/me", headers=headers("no-permission-token"))
        assert response.status_code == 403
        assert response.json()["code"] == "WORKSPACE_ACCESS_DENIED"
    finally:
        with psycopg.connect(admin_dsn()) as connection:
            connection.execute(
                "UPDATE memberships SET status='ACTIVE' WHERE id=%s",
                (NO_PERMISSION_MEMBERSHIP,),
            )


def test_correlation_id_is_propagated(api: TestClient) -> None:
    correlation_id = str(uuid4())
    request_headers = headers()
    request_headers["X-Correlation-ID"] = correlation_id
    response = api.get("/api/v1/me", headers=request_headers)
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == correlation_id
