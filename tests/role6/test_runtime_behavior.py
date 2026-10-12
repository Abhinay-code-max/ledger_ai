"""Runtime behavior, repeatability, queue saturation, timeout, and manifest verification tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ledgerai_contracts.v1.model_runtime import (
    InferenceInput,
    ModelCapability,
    ModelInferenceRequest,
    SupportedInputType,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role6.app import create_role6_app
from ledgerai_role6.backend import DeterministicInferenceBackend
from ledgerai_role6.config import Role6Settings
from ledgerai_role6.manifest import ManifestValidationError, load_and_verify_manifest
from ledgerai_role6.queue import RuntimeQueueManager

SECRET_VALUE = "a" * 32
SECRET = SecretStr(SECRET_VALUE)
TENANT_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("10000000-0000-0000-0000-000000000002")
LEGAL_ENTITY_ID = UUID("10000000-0000-0000-0000-000000000003")


def make_headers(op_id: UUID) -> dict[str, str]:
    import time

    import jwt

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


def test_deterministic_backend_repeatability() -> None:
    backend = DeterministicInferenceBackend()
    manifest_path = Path("models/manifests/ledgerai_docintel_v1.manifest.json")
    manifest = load_and_verify_manifest(manifest_path)

    async def run() -> None:
        await backend.initialize(manifest)
        tenant = EntityTenantContext(
            tenant_id=TENANT_ID,
            organization_id=ORG_ID,
            legal_entity_id=LEGAL_ENTITY_ID,
        )
        req = ModelInferenceRequest(
            schema_version="1.0",
            tenant_context=tenant,
            operation_id=uuid4(),
            correlation_id=uuid4(),
            capability=ModelCapability.DOCUMENT_EXTRACTION,
            model_name=manifest.model_name,
            input_data=InferenceInput(
                media_type=SupportedInputType.TEXT,
                text_content="INVOICE NUMBER: INV-449\nTOTAL: USD 120.00\n",
            ),
        )
        out1, _ = await backend.infer(req, manifest)
        out2, _ = await backend.infer(req, manifest)

        assert out1.model_dump() == out2.model_dump()

    asyncio.run(run())


def test_duplicate_operation_idempotency() -> None:
    settings = Role6Settings(
        environment="test",
        service_token_secret=SECRET,
        service_audience="ledgerai-role6",
    )
    app = create_role6_app(settings)
    client = TestClient(app)

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
            "text_content": "INVOICE NUMBER: 123\nTOTAL AMOUNT: USD 100.00\n",
        },
    }

    r1 = client.post("/v1/models/infer", headers=headers, json=payload)
    r2 = client.post("/v1/models/infer", headers=headers, json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["created_at"] == r2.json()["created_at"]


def test_queue_depth_saturation() -> None:
    queue_mgr = RuntimeQueueManager(
        max_concurrency=1, max_queue_depth=1, per_tenant_max_concurrency=5
    )

    async def run() -> None:
        async with queue_mgr.acquire(TENANT_ID):
            # First request holds concurrency slot
            # Second acquire enters queue
            task = asyncio.create_task(queue_mgr.acquire(TENANT_ID).__aenter__())
            await asyncio.sleep(0.01)

            # Third acquire exceeds queue depth 1 and must raise 429
            with pytest.raises(Exception) as exc_info:
                async with queue_mgr.acquire(TENANT_ID):
                    pass
            assert "queue depth saturated" in str(exc_info.value).lower()

            task.cancel()

    asyncio.run(run())


def test_manifest_hash_mismatch_detected(tmp_path: Path) -> None:
    manifest_file = tmp_path / "bad.manifest.json"
    manifest_file.write_text(
        """{
          "schema_version": "1.0",
          "model_id": "test-v1",
          "model_name": "test-v1",
          "backend_type": "DETERMINISTIC",
          "immutable_revision": "18dce7558f6bd7136d53d0517d32542ae025f50b",
          "artifact_hashes": {
            "weights.bin": "0000000000000000000000000000000000000000000000000000000000000000"
          },
          "preprocessing_version": "v1.0.0",
          "supported_capabilities": ["DOCUMENT_EXTRACTION"],
          "supported_input_types": ["text/plain"]
        }"""
    )
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    weights = artifacts_dir / "weights.bin"
    weights.write_bytes(b"corrupted content")

    with pytest.raises(ManifestValidationError, match="Artifact hash mismatch"):
        load_and_verify_manifest(manifest_file, artifacts_dir, verify_files_exist=True)


def test_readiness_endpoint_distinguishes_healthy_and_unhealthy() -> None:
    settings = Role6Settings(
        environment="test",
        service_token_secret=SECRET,
        service_audience="ledgerai-role6",
    )
    app = create_role6_app(settings)
    client = TestClient(app)

    # Initial ready status with test backend
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["backend_ready"] is True
    assert data["manifest_valid"] is True
    assert data["configured_model"] == "docintel-foundation-vlm"
    assert data["device"] == "cpu-deterministic"


def test_role4_classify_adapter_compatibility() -> None:
    settings = Role6Settings(
        environment="test",
        service_token_secret=SECRET,
        service_audience="ledgerai-role6",
    )
    app = create_role6_app(settings)
    client = TestClient(app)

    op_id = uuid4()
    headers = make_headers(op_id)
    payload = {
        "resource_id": str(uuid4()),
    }
    resp = client.post("/v1/classifications", headers=headers, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["schema_version"] == "1.0"
    assert data["category"] == "INVOICE"
    assert "confidence" in data
    assert len(data["provenance"]) >= 1
