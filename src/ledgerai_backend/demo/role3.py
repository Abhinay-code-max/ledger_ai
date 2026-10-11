"""Deterministic protocol-faithful Role 3 service stub for the synthetic demo."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID

import jwt
from fastapi import FastAPI, Header, HTTPException, Request

from ledgerai_backend.database.seed import stable_id


def _secret() -> str:
    value = os.environ.get("LEDGERAI_SERVICE_TOKEN_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("LEDGERAI_SERVICE_TOKEN_SECRET must contain at least 32 characters")
    return value


def _authenticate(value: str | None) -> None:
    if not value or not value.startswith("Bearer "):
        raise HTTPException(401, "service authentication required")
    try:
        jwt.decode(
            value[7:],
            _secret(),
            algorithms=["HS256"],
            audience="ledgerai-role3",
            issuer=os.environ.get("LEDGERAI_SERVICE_TOKEN_ISSUER", "ledgerai-backend"),
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, "service authentication failed") from exc


def _producer() -> dict[str, object]:
    return {
        "producer_type": "SERVICE",
        "name": "ledgerai-demo-role3",
        "version": "1.0.0",
        "algorithm_version": "nova-deterministic-v1",
    }


def _correlation(payload: dict[str, object]) -> dict[str, object]:
    value = payload.get("correlation")
    if isinstance(value, dict):
        return value
    operation_id = str(payload.get("operation_id", stable_id("nova:demo:match")))
    return {"request_id": operation_id, "correlation_id": operation_id, "causation_id": None}


def create_demo_role3_app() -> FastAPI:
    app = FastAPI(title="LedgerAI NOVA demo Role 3", docs_url=None, redoc_url=None)

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/v1/reconciliations")
    async def reconcile(
        request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, object]:
        _authenticate(authorization)
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(422, "object payload required")
        tenant_context = payload["tenant_context"]
        assert isinstance(tenant_context, dict)
        transaction_ids = [UUID(str(tx)) for tx in payload.get("transaction_ids", [])]
        now = datetime.now(UTC).isoformat()
        match_id = str(stable_id("nova:demo:match"))
        exception_id = str(stable_id("nova:demo:exception"))
        corr = _correlation(payload)
        records = [
            {
                "resource_type": "bank_transaction",
                "resource_id": str(tx_id),
                "resource_version": "1",
            }
            for tx_id in transaction_ids
        ]
        if "document_extraction_id" in payload:
            records.append(
                {
                    "resource_type": "document_extraction",
                    "resource_id": str(payload["document_extraction_id"]),
                    "resource_version": "1",
                }
            )

        proposal = {
            "schema_version": "1.0",
            "proposal_id": match_id,
            "proposal_version": 1,
            "tenant_context": tenant_context,
            "records": records,
            "match_type": "ONE_TO_ONE",
            "confidence": "0.99",
            "score": "0.99",
            "reasons": [
                {
                    "code": "AMOUNT_AND_REFERENCE_MATCH",
                    "contribution": "0.99",
                    "explanation": "Synthetic clean match for INR 1250.00",
                }
            ],
            "conflicts": [],
            "producer": _producer(),
            "status": "REVIEW_REQUIRED",
            "created_at": now,
            "correlation": corr,
        }

        # The planted exception: AMOUNT_MISMATCH
        exception = {
            "schema_version": "1.0",
            "exception_id": exception_id,
            "tenant_context": tenant_context,
            "exception_type": "AMOUNT_MISMATCH",
            "severity": "HIGH",
            "involved_resources": records,
            "explanation": "Synthetic planted INR 50.00 mismatch requires human resolution.",
            "reason_codes": ["PLANTED_AMOUNT_MISMATCH"],
            "supporting_evidence": [],
            "suggested_action": "Review source evidence",
            "required_action": "HUMAN_REVIEW",
            "resolution_status": "OPEN",
            "resolution_reference": None,
            "detector": {
                "producer_type": "SERVICE",
                "name": "ledgerai-demo-role3",
                "version": "1.0.0",
                "rule_or_policy_version": "nova-exception-v1",
            },
            "created_at": now,
            "updated_at": now,
            "correlation": corr,
        }

        return {
            "schema_version": "1.0",
            "tenant_context": tenant_context,
            "proposal": proposal,
            "exceptions": [exception],
        }

    return app


app = create_demo_role3_app()
