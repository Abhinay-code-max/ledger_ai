"""Deterministic protocol-faithful Role 1 service stub for the synthetic demo."""

from __future__ import annotations

from datetime import UTC, datetime

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
