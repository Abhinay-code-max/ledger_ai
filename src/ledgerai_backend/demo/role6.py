"""Deterministic, protocol-faithful Role 6 classification stub for NOVA."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request

from ledgerai_backend.demo.service_auth import authenticated_payload


def create_demo_role6_app() -> FastAPI:
    app = FastAPI(title="LedgerAI NOVA demo Role 6", docs_url=None, redoc_url=None)

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/v1/classifications")
    async def classify(request: Request) -> dict[str, object]:
        payload = await authenticated_payload(request, audience="ledgerai-role6")
        resource_id = payload.get("resource_id")
        if resource_id is None:
            raise HTTPException(422, "resource_id is required")
        return {
            "schema_version": "1.0",
            "tenant_context": payload["tenant_context"],
            "resource_id": resource_id,
            "category": "INVOICE",
            "confidence": "0.99",
            "provenance": [
                {
                    "producer": "ledgerai-demo-role6",
                    "producer_version": "1.0.0",
                    "model_version": "nova-deterministic-v1",
                }
            ],
        }

    return app

app = create_demo_role6_app()
