"""Live HTTP service boundary integration tests for Roles 1, 2, 3, 4, 6, Postgres, Redis, and MinIO."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pytest
from phase1_postgres_support import admin_dsn, runtime_dsn

from ledgerai_backend.core.identity import DeterministicTestIdentityProvider, VerifiedIdentity
from ledgerai_backend.demo.reset import (
    NOVA_ENTITY_ID,
    NOVA_ORGANIZATION_ID,
    NOVA_TENANT_ID,
    reset_nova_demo,
)
from ledgerai_backend.demo.role1 import create_demo_role1_app
from ledgerai_backend.demo.role2 import create_demo_role2_app
from ledgerai_backend.demo.role3 import create_demo_role3_app
from ledgerai_backend.demo.role6 import create_demo_role6_app
from ledgerai_backend.demo.runner import DATASET, LiveServer, _settings
from ledgerai_backend.integration.adapters import (
    AdapterSecurity,
    Role6Adapter,
    SignedServiceTokenProvider,
)
from ledgerai_backend.main import create_app

pytestmark = pytest.mark.postgres

ISSUER = "https://identity.demo.invalid/"
SERVICE_SECRET = "synthetic-service-secret-for-nova-0001"


def _configure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERAI_ENVIRONMENT", "test")
    monkeypatch.setenv("LEDGERAI_DEMO_ENABLED", "true")
    monkeypatch.setenv("LEDGERAI_DEMO_RESET_CONFIRM", "RESET_NOVA_ONLY")
    monkeypatch.setenv("LEDGERAI_DEMO_MAKER_TOKEN", "synthetic-maker-token-for-nova")
    monkeypatch.setenv("LEDGERAI_DEMO_REVIEWER_TOKEN", "synthetic-reviewer-token-for-nova")
    monkeypatch.setenv("LEDGERAI_SERVICE_TOKEN_SECRET", SERVICE_SECRET)
    monkeypatch.setenv(
        "LEDGERAI_STORAGE_ENDPOINT_URL", os.environ["LEDGERAI_TEST_STORAGE_ENDPOINT_URL"]
    )
    monkeypatch.setenv(
        "LEDGERAI_STORAGE_ACCESS_KEY", os.environ["LEDGERAI_TEST_STORAGE_ACCESS_KEY"]
    )
    monkeypatch.setenv(
        "LEDGERAI_STORAGE_SECRET_KEY", os.environ["LEDGERAI_TEST_STORAGE_SECRET_KEY"]
    )
    monkeypatch.setenv("LEDGERAI_REDIS_URL", os.environ["LEDGERAI_TEST_REDIS_URL"])
    monkeypatch.setenv(
        "LEDGERAI_DATABASE_DSN",
        runtime_dsn().replace("postgresql://", "postgresql+psycopg://", 1),
    )
    monkeypatch.setenv(
        "LEDGERAI_MIGRATION_DSN",
        admin_dsn().replace("postgresql://", "postgresql+psycopg://", 1),
    )


@pytest.fixture
def live_services(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, str]]:
    """Spins up all actual HTTP service boundaries on distinct loopback ports."""
    _configure_env(monkeypatch)
    role1_url = "http://127.0.0.1:8101"
    role2_url = "http://127.0.0.1:8102"
    role3_url = "http://127.0.0.1:8103"
    role6_url = "http://127.0.0.1:8006"
    api_url = "http://127.0.0.1:8100"

    settings = _settings(role1_url, role2_url, role3_url, role6_url)
    identity_provider = DeterministicTestIdentityProvider(
        {
            "synthetic-maker-token-for-nova": VerifiedIdentity(ISSUER, "nova-admin"),
            "synthetic-reviewer-token-for-nova": VerifiedIdentity(ISSUER, "nova-reviewer"),
        }
    )

    apps = [
        (create_demo_role1_app(), role1_url),
        (create_demo_role2_app(), role2_url),
        (create_demo_role3_app(), role3_url),
        (create_demo_role6_app(), role6_url),
        (create_app(settings, identity_provider=identity_provider), api_url),
    ]

    with ExitStack() as stack:
        for app, url in apps:
            parsed = urlparse(url)
            stack.enter_context(LiveServer(app, parsed.hostname or "127.0.0.1", parsed.port or 80))
        yield {
            "role1": role1_url,
            "role2": role2_url,
            "role3": role3_url,
            "role6": role6_url,
            "api": api_url,
        }


def test_live_service_boundaries_and_contract_invariants(
    live_services: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify live HTTP boundaries for Roles 1, 2, 3, 4, 6 with bound tenant, audience, and ops."""
    _configure_env(monkeypatch)
    role1_url = live_services["role1"]
    role2_url = live_services["role2"]
    role3_url = live_services["role3"]
    role6_url = live_services["role6"]
    api_url = live_services["api"]

    # 1. Verify health/readiness over HTTP for all 5 services
    with httpx.Client(timeout=5.0) as client:
        r1_ready = client.get(f"{role1_url}/health/ready")
        assert r1_ready.status_code == 200

        r2_ready = client.get(f"{role2_url}/health/ready")
        assert r2_ready.status_code == 200

        r3_ready = client.get(f"{role3_url}/health/ready")
        assert r3_ready.status_code == 200

        r6_ready = client.get(f"{role6_url}/health/ready")
        assert r6_ready.status_code == 200
        assert r6_ready.json()["backend_ready"] is True

        api_live = client.get(f"{api_url}/health/live")
        assert api_live.status_code == 200

    # 2. Reset NOVA demo tenant safely
    settings = _settings(role1_url, role2_url, role3_url, role6_url)
    reset = reset_nova_demo(settings, confirmed=True)
    assert reset["tenant_id"] == str(NOVA_TENANT_ID)

    # 3. Role 4 calls Role 6 over HTTP via typed Role6Adapter
    token_provider = SignedServiceTokenProvider(
        issuer="ledgerai-backend",
        subject="ledgerai-backend",
        secret=SERVICE_SECRET,
    )
    security = AdapterSecurity(
        base_url=role6_url,
        audience="ledgerai-role6",
        environment="test",
    )
    adapter = Role6Adapter(security, token_provider)
    from ledgerai_contracts.v1.tenancy import EntityTenantContext

    tenant_context = EntityTenantContext(
        tenant_id=NOVA_TENANT_ID,
        organization_id=NOVA_ORGANIZATION_ID,
        legal_entity_id=NOVA_ENTITY_ID,
    )
    op_id = uuid4()
    corr_id = uuid4()

    import asyncio

    async def verify_role6_adapter() -> None:
        try:
            # Classify over HTTP
            clf = await adapter.classify(
                payload={"resource_id": str(uuid4())},
                tenant_context=tenant_context,
                operation_id=op_id,
                correlation_id=corr_id,
            )
            assert clf.category == "INVOICE"
            assert clf.confidence == "0.99"

            # Manifest over HTTP
            manifest = await adapter.manifest(
                tenant_context=tenant_context,
                operation_id=op_id,
                correlation_id=corr_id,
            )
            assert manifest.model_name == "docintel-foundation-vlm"
        finally:
            await adapter.aclose()

    asyncio.run(verify_role6_adapter())

    # 4. Execute the complete business lifecycle through Role 4 API
    correlation_id = str(uuid4())
    maker_token = "synthetic-maker-token-for-nova"
    reviewer_token = "synthetic-reviewer-token-for-nova"

    headers_maker = {
        "Authorization": f"Bearer {maker_token}",
        "X-Workspace-Code": "nova",
        "X-Organization-ID": str(NOVA_ORGANIZATION_ID),
        "X-Legal-Entity-ID": str(NOVA_ENTITY_ID),
        "X-Correlation-ID": correlation_id,
    }
    headers_reviewer = {
        "Authorization": f"Bearer {reviewer_token}",
        "X-Workspace-Code": "nova",
        "X-Organization-ID": str(NOVA_ORGANIZATION_ID),
        "X-Legal-Entity-ID": str(NOVA_ENTITY_ID),
        "X-Correlation-ID": correlation_id,
    }

    with httpx.Client(base_url=api_url, timeout=10.0) as client:
        # Upload evidence
        evidence = (DATASET / "documents" / "NOVA_SYNTHETIC_INVOICE_001.pdf").read_bytes()
        import hashlib

        digest = hashlib.sha256(evidence).hexdigest()
        up_resp = client.post(
            "/api/v1/documents/uploads",
            headers={**headers_maker, "Idempotency-Key": "live-bound-upload"},
            json={
                "original_filename": "NOVA_SYNTHETIC_INVOICE_001.pdf",
                "media_type": "application/pdf",
                "byte_size": len(evidence),
                "sha256": digest,
            },
        )
        assert up_resp.status_code == 201
        upload = up_resp.json()

        # MinIO upload
        put_resp = httpx.put(
            str(upload["upload_url"]),
            content=evidence,
            headers={
                "Content-Type": "application/pdf",
                "x-amz-meta-expected-size": str(len(evidence)),
                "x-amz-server-side-encryption": "AES256",
            },
            timeout=10.0,
        )
        assert put_resp.status_code in {200, 201}

        # Complete upload
        comp_resp = client.post(
            f"/api/v1/documents/uploads/{upload['upload_id']}/complete",
            headers={**headers_maker, "Idempotency-Key": "live-bound-comp"},
            json={"sha256": digest, "byte_size": len(evidence)},
        )
        assert comp_resp.status_code == 200
        doc = comp_resp.json()
        doc_id = doc["id"]

        # Import bank transactions
        csv_data = (DATASET / "bank-transactions.csv").read_bytes()
        from ledgerai_backend.database.seed import stable_id

        imp_resp = client.post(
            "/api/v1/transaction-imports",
            headers={**headers_maker, "Idempotency-Key": "live-bound-import"},
            data={
                "bank_account_id": str(stable_id("nova:demo:bank-account")),
                "mapping_json": "{}",
            },
            files={"file": ("bank-transactions.csv", csv_data, "text/csv")},
        )
        assert imp_resp.status_code == 201
        imported = imp_resp.json()

        txs_resp = client.get(
            "/api/v1/transactions",
            params={"import_id": imported["id"]},
            headers=headers_maker,
        )
        assert txs_resp.status_code == 200
        transactions = txs_resp.json()["items"]
        assert len(transactions) == 2

        # Role 4 invokes extraction: Role 4 -> Role 1 -> Role 6 over HTTP
        ext_resp = client.post(
            f"/api/v1/documents/{doc_id}/extractions",
            headers={**headers_maker, "Idempotency-Key": "live-bound-extract"},
        )
        assert ext_resp.status_code == 201
        assert ext_resp.json()["status"] == "COMPLETED"

        # Reconcile via Role 3: planted INR 50.00 mismatch
        rec_resp = client.post(
            "/api/v1/reconciliations",
            headers={**headers_maker, "Idempotency-Key": "live-bound-reconcile"},
            json={
                "document_id": doc_id,
                "document_version_id": doc["current_version_id"],
                "transaction_ids": [t["id"] for t in transactions],
            },
        )
        assert rec_resp.status_code == 201
        reconciliation = rec_resp.json()
        exception_id = reconciliation["exception_id"]
        assert exception_id is not None
        approval_id = reconciliation["approval_request_id"]
        journal_proposal_id = reconciliation["journal_proposal_id"]

        exc_resp = client.get(f"/api/v1/exceptions/{exception_id}", headers=headers_maker)
        assert exc_resp.status_code == 200
        exc = exc_resp.json()
        assert exc["exception_type"] == "AMOUNT_MISMATCH"
        assert exc["severity"] == "HIGH"

        # Reviewer resolves exception
        res_resp = client.post(
            f"/api/v1/exceptions/{exception_id}/resolve",
            headers={**headers_reviewer, "Idempotency-Key": "live-bound-resolve"},
            json={"reason": "Resolved planted INR 50.00 mismatch row."},
        )
        assert res_resp.status_code == 200

        # Reviewer approves
        appr_resp = client.post(
            f"/api/v1/approval-requests/{approval_id}/approve",
            headers={
                **headers_reviewer,
                "Idempotency-Key": "live-bound-approve",
                "If-Match": "1",
            },
            json={"reviewed_resource_version": "1", "reason": "Approved by reviewer"},
        )
        assert appr_resp.status_code == 200

        # Role 4 invokes Role 2: period creation and journal posting
        per_resp = client.post(
            "/api/v1/accounting-periods",
            headers=headers_maker,
            json={"period_start": "2026-09-01", "period_end": "2026-09-30", "currency": "INR"},
        )
        assert per_resp.status_code == 201
        period = per_resp.json()

        post_resp = client.post(
            "/api/v1/posting-operations",
            headers={**headers_maker, "Idempotency-Key": "live-bound-post"},
            json={
                "journal_proposal_id": journal_proposal_id,
                "proposal_version": 1,
                "accounting_period_id": period["id"],
            },
        )
        assert post_resp.status_code == 202
        assert post_resp.json()["state"] == "CONFIRMED"

        # Role 4 invokes Role 2: close accounting period
        close_resp = client.post(
            f"/api/v1/accounting-periods/{period['id']}/close",
            headers={**headers_maker, "Idempotency-Key": "live-bound-close"},
        )
        assert close_resp.status_code == 202
        assert close_resp.json()["state"] == "CONFIRMED"

        # Role 4 invokes Role 2: statement generation
        for st in ("TRIAL_BALANCE", "PROFIT_AND_LOSS", "BALANCE_SHEET"):
            st_resp = client.post(
                f"/api/v1/accounting-periods/{period['id']}/statements/{st}",
                headers=headers_maker,
            )
            assert st_resp.status_code == 201
            data = st_resp.json()
            assert data["currency"] == "INR"
            assert data["role2_version"] == "1.0.0"
            assert len(data["lines"]) > 0
