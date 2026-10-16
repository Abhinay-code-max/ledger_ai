"""Live HTTP proof and integration test suite for Role 6 Model Gateway."""

from __future__ import annotations

import time
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from pydantic import SecretStr

from ledgerai_backend.demo.runner import LiveServer
from ledgerai_backend.integration.adapters import (
    AdapterSecurity,
    Role6Adapter,
    SignedServiceTokenProvider,
)
from ledgerai_contracts.v1.model_runtime import (
    InferenceInput,
    ModelCapability,
    ModelInferenceRequest,
    ModelInferenceResponse,
    SupportedInputType,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role6.app import create_role6_app
from ledgerai_role6.config import Role6Settings
from ledgerai_role6.manifest import load_and_verify_manifest

SECRET_KEY = "local-service-token-secret-32-chars-minimum"
SECRET = SecretStr(SECRET_KEY)
TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
ORG_ID = UUID("22222222-2222-2222-2222-222222222222")
LEGAL_ENTITY_ID = UUID("33333333-3333-3333-3333-333333333333")


def make_token(
    *,
    issuer: str = "ledgerai-backend",
    subject: str = "role4-backend",
    audience: str = "ledgerai-role6",
    tenant_id: UUID = TENANT_ID,
    operation_id: UUID | None = None,
    ttl: int = 60,
    expired: bool = False,
) -> str:
    now = int(time.time())
    iat = now - 120 if expired else now
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
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


@pytest.fixture(scope="module")
def live_role6_server() -> Iterator[str]:
    """Start real Role 6 HTTP service with live loopback server on ephemeral port."""
    settings = Role6Settings(
        environment="test",
        service_token_secret=SECRET,
        service_audience="ledgerai-role6",
        active_backend="deterministic",
        max_request_bytes=5000,
        max_concurrency=2,
        max_queue_depth=2,
    )
    manifest = load_and_verify_manifest(
        Path("models/manifests/ledgerai_docintel_v1.manifest.json"),
        Path("models/artifacts"),
        verify_files_exist=False,
    )
    manifest = manifest.model_copy(
        update={"limits": manifest.limits.model_copy(update={"max_request_bytes": 5000})}
    )
    app = create_role6_app(settings, manifest=manifest)
    server = LiveServer(app, "127.0.0.1", 8096)
    with server:
        yield "http://127.0.0.1:8096"


@pytest.mark.asyncio
async def test_live_health_endpoints(live_role6_server: str) -> None:
    base_url = live_role6_server
    async with httpx.AsyncClient(base_url=base_url) as client:
        # GET /health/live
        live_resp = await client.get("/health/live")
        assert live_resp.status_code == 200
        assert live_resp.json() == {"status": "live"}

        # GET /health/ready
        ready_resp = await client.get("/health/ready")
        assert ready_resp.status_code == 200
        data = ready_resp.json()
        assert data["status"] == "healthy"
        assert data["backend_ready"] is True
        assert data["manifest_valid"] is True


@pytest.mark.asyncio
async def test_live_manifest_endpoint(live_role6_server: str) -> None:
    base_url = live_role6_server
    op_id = uuid4()
    corr_id = uuid4()
    token = make_token(operation_id=op_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(corr_id),
    }
    async with httpx.AsyncClient(base_url=base_url) as client:
        resp = await client.get("/v1/models/manifest", headers=headers)
        assert resp.status_code == 200
        manifest = resp.json()
        assert manifest["model_name"] == "docintel-foundation-vlm"
        assert manifest["backend_type"] == "DETERMINISTIC"


@pytest.mark.asyncio
async def test_role1_to_role6_inference_live(live_role6_server: str) -> None:
    """Prove serialized HTTP call from Role 1 client context to Role 6."""
    base_url = live_role6_server
    op_id = uuid4()
    corr_id = uuid4()
    token = make_token(
        issuer="ledgerai-role1",
        subject="ledgerai-role1",
        operation_id=op_id,
    )
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
            "text_content": "Invoice INVOICE-2026-001 total amount 1250.00 INR",
        },
        "temperature": "0.0",
    }
    async with httpx.AsyncClient(base_url=base_url) as client:
        resp = await client.post("/v1/models/infer", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        response_model = ModelInferenceResponse.model_validate(data)
        assert response_model.operation_id == op_id
        assert response_model.correlation_id == corr_id
        assert response_model.execution_metadata.backend_type == "DETERMINISTIC"
        assert len(response_model.output.fields) > 0


@pytest.mark.asyncio
async def test_role4_adapter_to_role6_classification_live(live_role6_server: str) -> None:
    """Prove Role4Adapter classification and infer workflow over live HTTP boundary."""
    token_provider = SignedServiceTokenProvider(
        issuer="ledgerai-backend",
        subject="ledgerai-backend",
        secret=SECRET_KEY,
    )
    security = AdapterSecurity(
        base_url=live_role6_server,
        audience="ledgerai-role6",
        environment="test",
    )
    adapter = Role6Adapter(security, token_provider)
    tenant_context = EntityTenantContext(
        tenant_id=TENANT_ID,
        organization_id=ORG_ID,
        legal_entity_id=LEGAL_ENTITY_ID,
    )
    op_id = uuid4()
    corr_id = uuid4()
    res_id = uuid4()

    try:
        # 1. Classification via Role6Adapter
        result = await adapter.classify(
            payload={"resource_id": str(res_id)},
            tenant_context=tenant_context,
            operation_id=op_id,
            correlation_id=corr_id,
        )
        assert result.schema_version == "1.0"
        assert result.category == "INVOICE"
        assert result.confidence == "0.99"
        assert result.resource_id == res_id

        # 2. Health check via Role6Adapter
        ready = await adapter.health_ready()
        assert ready.status == "healthy"
        assert ready.backend_ready is True

        # 3. Manifest via Role6Adapter
        manifest = await adapter.manifest(
            tenant_context=tenant_context,
            operation_id=op_id,
            correlation_id=corr_id,
        )
        assert manifest.model_name == "docintel-foundation-vlm"

        # 4. Infer via Role6Adapter
        infer_op = uuid4()
        req = ModelInferenceRequest(
            schema_version="1.0",
            tenant_context=tenant_context,
            operation_id=infer_op,
            correlation_id=corr_id,
            capability=ModelCapability.DOCUMENT_EXTRACTION,
            model_name="docintel-foundation-vlm",
            input_data=InferenceInput(
                media_type=SupportedInputType.TEXT,
                text_content="Vendor Alpha receipt total 999.00 USD",
            ),
            temperature=Decimal("0.0"),
        )
        infer_res = await adapter.infer(
            payload=req,
            tenant_context=tenant_context,
            operation_id=infer_op,
            correlation_id=corr_id,
        )
        assert infer_res.operation_id == infer_op
        assert infer_res.output.fields is not None
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_security_rejections_live(live_role6_server: str) -> None:
    """Verify wrong audience, wrong tenant, wrong operation, and expired token rejections."""
    base_url = live_role6_server
    op_id = uuid4()
    corr_id = uuid4()

    async with httpx.AsyncClient(base_url=base_url) as client:
        # 1. Wrong audience
        wrong_aud_token = make_token(audience="ledgerai-role1", operation_id=op_id)
        resp = await client.post(
            "/v1/classifications",
            headers={
                "Authorization": f"Bearer {wrong_aud_token}",
                "X-Tenant-ID": str(TENANT_ID),
                "X-Organization-ID": str(ORG_ID),
                "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
                "X-Operation-ID": str(op_id),
                "X-Correlation-ID": str(corr_id),
            },
            json={"resource_id": str(uuid4())},
        )
        assert resp.status_code == 403

        # 2. Wrong tenant
        other_tenant = uuid4()
        mismatch_tenant_token = make_token(tenant_id=other_tenant, operation_id=op_id)
        resp = await client.post(
            "/v1/classifications",
            headers={
                "Authorization": f"Bearer {mismatch_tenant_token}",
                "X-Tenant-ID": str(TENANT_ID),
                "X-Organization-ID": str(ORG_ID),
                "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
                "X-Operation-ID": str(op_id),
                "X-Correlation-ID": str(corr_id),
            },
            json={"resource_id": str(uuid4())},
        )
        assert resp.status_code == 403

        # 3. Wrong operation
        other_op = uuid4()
        mismatch_op_token = make_token(operation_id=other_op)
        resp = await client.post(
            "/v1/classifications",
            headers={
                "Authorization": f"Bearer {mismatch_op_token}",
                "X-Tenant-ID": str(TENANT_ID),
                "X-Organization-ID": str(ORG_ID),
                "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
                "X-Operation-ID": str(op_id),
                "X-Correlation-ID": str(corr_id),
            },
            json={"resource_id": str(uuid4())},
        )
        assert resp.status_code == 403

        # 4. Expired token
        expired_token = make_token(expired=True, operation_id=op_id)
        resp = await client.post(
            "/v1/classifications",
            headers={
                "Authorization": f"Bearer {expired_token}",
                "X-Tenant-ID": str(TENANT_ID),
                "X-Organization-ID": str(ORG_ID),
                "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
                "X-Operation-ID": str(op_id),
                "X-Correlation-ID": str(corr_id),
            },
            json={"resource_id": str(uuid4())},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_oversized_and_unavailable_model_live(live_role6_server: str) -> None:
    base_url = live_role6_server
    op_id = uuid4()
    corr_id = uuid4()
    token = make_token(operation_id=op_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(TENANT_ID),
        "X-Organization-ID": str(ORG_ID),
        "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
        "X-Operation-ID": str(op_id),
        "X-Correlation-ID": str(corr_id),
    }

    async with httpx.AsyncClient(base_url=base_url) as client:
        # Oversized request
        huge_payload = {
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
            "input_data": {"media_type": "text/plain", "text_content": "X" * 6000},
            "temperature": "0.0",
        }
        resp = await client.post("/v1/models/infer", json=huge_payload, headers=headers)
        assert resp.status_code == 413

        # Unavailable model
        unavail_payload = {
            "schema_version": "1.0",
            "tenant_context": {
                "tenant_id": str(TENANT_ID),
                "organization_id": str(ORG_ID),
                "legal_entity_id": str(LEGAL_ENTITY_ID),
            },
            "operation_id": str(op_id),
            "correlation_id": str(corr_id),
            "capability": "DOCUMENT_EXTRACTION",
            "model_name": "unknown-nonexistent-model",
            "input_data": {"media_type": "text/plain", "text_content": "Sample text"},
            "temperature": "0.0",
        }
        resp = await client.post("/v1/models/infer", json=unavail_payload, headers=headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deterministic_repeatability_live(live_role6_server: str) -> None:
    """Verify deterministic repeatability: identical inputs yield identical response bodies."""
    base_url = live_role6_server
    async with httpx.AsyncClient(base_url=base_url) as client:
        responses = []
        for _ in range(2):
            op_id = uuid4()
            corr_id = uuid4()
            token = make_token(operation_id=op_id)
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
                    "text_content": "Invoice 12345 total 500.00",
                },
                "temperature": "0.0",
            }
            resp = await client.post("/v1/models/infer", json=payload, headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            responses.append(data["output"])

        assert responses[0] == responses[1]


@pytest.mark.asyncio
async def test_role1_http_service_calls_role6_http_service(
    live_role6_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify live HTTP chain: Caller -> Role 1 HTTP server -> Role 6 HTTP server."""
    from ledgerai_backend.demo.role1 import create_demo_role1_app

    monkeypatch.setenv("LEDGERAI_DEMO_ROLE6_URL", live_role6_server)
    monkeypatch.setenv("LEDGERAI_SERVICE_TOKEN_SECRET", SECRET_KEY)
    monkeypatch.setenv("LEDGERAI_ROLE6_SERVICE_TOKEN_SECRET", SECRET_KEY)
    role1_app = create_demo_role1_app()
    server1 = LiveServer(role1_app, "127.0.0.1", 8109)
    with server1:
        role1_url = "http://127.0.0.1:8109"
        op_id = uuid4()
        corr_id = uuid4()
        token = make_token(
            issuer="ledgerai-backend",
            subject="ledgerai-backend",
            audience="ledgerai-role1",
            operation_id=op_id,
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": str(TENANT_ID),
            "X-Organization-ID": str(ORG_ID),
            "X-Legal-Entity-ID": str(LEGAL_ENTITY_ID),
            "X-Operation-ID": str(op_id),
            "X-Correlation-ID": str(corr_id),
        }
        payload = {
            "document_id": str(uuid4()),
            "document_version_id": "1",
            "tenant_context": {
                "tenant_id": str(TENANT_ID),
                "organization_id": str(ORG_ID),
                "legal_entity_id": str(LEGAL_ENTITY_ID),
            },
            "operation_id": str(op_id),
            "correlation": {
                "request_id": str(op_id),
                "correlation_id": str(corr_id),
                "causation_id": None,
            },
        }
        async with httpx.AsyncClient(base_url=role1_url) as client:
            resp = await client.post("/v1/extractions", json=payload, headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "COMPLETED"
            assert data["classification"] == "INVOICE"
            assert len(data["fields"]) >= 5
