from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from ledgerai_backend.core.config import Settings
from ledgerai_backend.main import create_app


def client() -> TestClient:
    return TestClient(
        create_app(
            Settings(
                environment="test",
                allowed_hosts=["testserver"],
                database_dsn=None,
            )
        )
    )


def test_liveness_version_and_unavailable_readiness() -> None:
    with client() as api:
        assert api.get("/health/live").json() == {"status": "ok"}
        assert api.get("/version").json() == {
            "service": "ledgerai-backend",
            "version": "1.1.0",
        }
        response = api.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable"}


def test_request_and_correlation_ids_are_validated_and_propagated() -> None:
    correlation_id = str(uuid4())
    with client() as api:
        response = api.get(
            "/health/live",
            headers={"X-Request-ID": "unsafe", "X-Correlation-ID": correlation_id},
        )
    UUID(response.headers["X-Request-ID"])
    assert response.headers["X-Correlation-ID"] == correlation_id


def test_missing_token_maps_to_phase0_error_envelope() -> None:
    with client() as api:
        response = api.get("/api/v1/me", headers={"X-Workspace-Code": "nova"})
    assert response.status_code == 401
    body = response.json()
    assert body["schema_version"] == "1.0"
    assert body["category"] == "AUTHENTICATION"
    assert body["code"] == "AUTHENTICATION_REQUIRED"
    assert "X-Request-ID" in response.headers


def test_request_size_limit_is_safe() -> None:
    app = create_app(
        Settings(
            environment="test",
            allowed_hosts=["testserver"],
            max_request_bytes=1024,
        )
    )
    with TestClient(app) as api:
        response = api.get("/health/live", headers={"content-length": "2048"})
    assert response.status_code == 413
    assert response.json()["code"] == "REQUEST_TOO_LARGE"
