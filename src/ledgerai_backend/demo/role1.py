"""Deterministic protocol-faithful Role 1 service stub for the synthetic demo."""

from __future__ import annotations

import os
import time
from contextlib import suppress
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import jwt
from fastapi import FastAPI, Request

from ledgerai_backend.database.seed import stable_id
from ledgerai_backend.demo.service_auth import authenticated_payload


def _producer() -> dict[str, str]:
    return {"producer_type": "SERVICE", "name": "ledgerai-demo-role1", "version": "1.0.0"}


def _correlation(payload: dict[str, object]) -> dict[str, object]:
    value = payload.get("correlation")
    if isinstance(value, dict):
        return value
    operation_id = str(payload.get("operation_id", stable_id("nova:demo:extraction")))
    return {"request_id": operation_id, "correlation_id": operation_id, "causation_id": None}


def create_demo_role1_app() -> FastAPI:
    app = FastAPI(title="LedgerAI NOVA demo Role 1", docs_url=None, redoc_url=None)

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/v1/extractions")
    async def extract(request: Request) -> dict[str, object]:
        payload = await authenticated_payload(request, audience="ledgerai-role1")
        tenant_context = payload["tenant_context"]
        assert isinstance(tenant_context, dict)
        doc_id = str(payload["document_id"])
        version_id = str(payload.get("document_version_id", "1"))

        # Role 1 invokes real Role 6 HTTP gateway for document intelligence model inference
        role6_url = os.environ.get("LEDGERAI_DEMO_ROLE6_URL", "http://127.0.0.1:8006").rstrip("/")
        service_secret = os.environ.get(
            "LEDGERAI_ROLE6_SERVICE_TOKEN_SECRET",
            os.environ.get(
                "LEDGERAI_SERVICE_TOKEN_SECRET", "local-service-token-secret-32-chars-minimum"
            ),
        )
        r6_op_id = uuid4()
        r6_corr_id = uuid4()
        now_ts = int(time.time())
        r6_token = jwt.encode(
            {
                "iss": "ledgerai-role1",
                "sub": "ledgerai-role1",
                "aud": "ledgerai-role6",
                "iat": now_ts,
                "exp": now_ts + 60,
                "tenant_id": str(tenant_context["tenant_id"]),
                "operation_id": str(r6_op_id),
            },
            service_secret,
            algorithm="HS256",
        )
        r6_headers = {
            "Authorization": f"Bearer {r6_token}",
            "X-Tenant-ID": str(tenant_context["tenant_id"]),
            "X-Organization-ID": str(tenant_context["organization_id"]),
            "X-Legal-Entity-ID": str(tenant_context["legal_entity_id"]),
            "X-Operation-ID": str(r6_op_id),
            "X-Correlation-ID": str(r6_corr_id),
        }
        r6_payload = {
            "schema_version": "1.0",
            "tenant_context": tenant_context,
            "operation_id": str(r6_op_id),
            "correlation_id": str(r6_corr_id),
            "capability": "DOCUMENT_EXTRACTION",
            "model_name": "docintel-foundation-vlm",
            "input_data": {
                "media_type": "text/plain",
                "text_content": f"Invoice document {doc_id} version {version_id}",
            },
            "temperature": "0.0",
        }
        with suppress(Exception):
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{role6_url}/v1/models/infer",
                    json=r6_payload,
                    headers=r6_headers,
                    timeout=2.0,
                )

        now = datetime.now(UTC).isoformat()
        extraction_id = str(stable_id("nova:demo:extraction"))
        evidence_hash = "a" * 64
        prov = [
            {
                "page_number": 1,
                "bounding_box": None,
                "source_document_id": doc_id,
                "document_version": version_id,
                "extraction_version": "1.0",
                "source_field": "invoice",
                "source_row": None,
                "human_correction_id": None,
                "confidence": "0.99",
                "evidence_hash": evidence_hash,
            }
        ]
        fields = [
            {
                "field_name": "invoice_number",
                "is_critical": True,
                "state": "EXTRACTED",
                "value": "NOVA-DEMO-INV-001",
                "confidence": "0.99",
                "provenance": prov,
            },
            {
                "field_name": "supplier_name",
                "is_critical": True,
                "state": "EXTRACTED",
                "value": "SYNTHETIC OFFICE SUPPLIES",
                "confidence": "0.99",
                "provenance": prov,
            },
            {
                "field_name": "invoice_date",
                "is_critical": True,
                "state": "EXTRACTED",
                "value": "2026-09-15",
                "confidence": "0.99",
                "provenance": prov,
            },
            {
                "field_name": "total",
                "is_critical": True,
                "state": "EXTRACTED",
                "value": "1250.00",
                "confidence": "0.99",
                "provenance": prov,
            },
            {
                "field_name": "currency",
                "is_critical": True,
                "state": "EXTRACTED",
                "value": "INR",
                "confidence": "0.99",
                "provenance": prov,
            },
        ]
        return {
            "schema_version": "1.0",
            "extraction_id": extraction_id,
            "document_id": doc_id,
            "document_version": "1",
            "tenant_context": tenant_context,
            "classification": "INVOICE",
            "fields": fields,
            "line_items": [],
            "validation_issues": [],
            "status": "COMPLETED",
            "review_disposition": "NOT_REQUIRED",
            "review_reason_codes": [],
            "producer": _producer(),
            "created_at": now,
            "updated_at": now,
            "correlation": _correlation(payload),
        }

    return app


app = create_demo_role1_app()
