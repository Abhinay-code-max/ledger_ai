"""Deterministic protocol-faithful Role 2 service for the synthetic demo only."""

from __future__ import annotations

import os
from datetime import UTC, datetime

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
            audience="ledgerai-role2",
            issuer=os.environ.get("LEDGERAI_SERVICE_TOKEN_ISSUER", "ledgerai-backend"),
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, "service authentication failed") from exc


def _producer() -> dict[str, str]:
    return {"producer_type": "SERVICE", "name": "ledgerai-demo-role2", "version": "1.0.0"}


def _correlation(payload: dict[str, object]) -> dict[str, object]:
    value = payload.get("correlation")
    if isinstance(value, dict):
        return value
    operation_id = str(payload["operation_id"])
    return {"request_id": operation_id, "correlation_id": operation_id, "causation_id": None}


def create_demo_role2_app() -> FastAPI:
    app = FastAPI(title="LedgerAI NOVA demo Role 2", docs_url=None, redoc_url=None)
    postings: dict[str, dict[str, object]] = {}
    closes: dict[str, dict[str, object]] = {}
    metrics = {"posting_mutations": 0, "posting_requests": 0}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    async def body(request: Request, authorization: str | None) -> dict[str, object]:
        _authenticate(authorization)
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(422, "object payload required")
        return payload

    @app.post("/v1/accounting-validations")
    async def validate_posting(
        request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, object]:
        payload = await body(request, authorization)
        proposal = payload["proposal"]
        assert isinstance(proposal, dict)
        return {
            "schema_version": "1.0",
            "tenant_context": payload["tenant_context"],
            "operation_id": payload["operation_id"],
            "proposal_id": proposal["resource_id"],
            "proposal_version": payload["proposal_version"],
            "outcome": "VALIDATED",
            "issues": [],
            "producer": _producer(),
            "correlation": _correlation(payload),
        }

    def posted(payload: dict[str, object]) -> dict[str, object]:
        proposal = payload["proposal"]
        assert isinstance(proposal, dict)
        operation_id = str(payload["operation_id"])
        posted_id = stable_id(f"nova:demo:posted:{operation_id}")
        return {
            "schema_version": "1.0",
            "tenant_context": payload["tenant_context"],
            "operation_id": operation_id,
            "proposal_id": proposal["resource_id"],
            "proposal_version": payload["proposal_version"],
            "outcome": "POSTED",
            "posted_journal_id": str(posted_id),
            "posted_at": datetime.now(UTC).isoformat(),
            "ledger_references": [
                {
                    "resource_type": "posted_journal",
                    "resource_id": str(posted_id),
                    "resource_version": "1",
                }
            ],
            "issues": [],
            "producer": _producer(),
            "correlation": _correlation(payload),
        }

    @app.post("/v1/journal-postings")
    async def post_journal(
        request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, object]:
        payload = await body(request, authorization)
        operation_id = str(payload["operation_id"])
        metrics["posting_requests"] += 1
        if operation_id not in postings:
            postings[operation_id] = posted(payload)
            metrics["posting_mutations"] += 1
        if os.environ.get("LEDGERAI_DEMO_UNKNOWN_POSTING", "false").lower() == "true":
            raise HTTPException(504, "synthetic unknown outcome")
        return postings[operation_id]

    @app.post("/v1/journal-posting-status")
    async def posting_status(
        request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, object]:
        payload = await body(request, authorization)
        operation_id = str(payload["operation_id"])
        result = postings.get(operation_id)
        if result is None:
            raise HTTPException(404, "operation not found")
        return result

    @app.post("/v1/period-close-validations")
    async def validate_close(
        request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, object]:
        payload = await body(request, authorization)
        return {
            "schema_version": "1.0",
            "tenant_context": payload["tenant_context"],
            "operation_id": payload["operation_id"],
            "accounting_period_id": payload["accounting_period_id"],
            "outcome": "VALIDATED",
            "issues": [],
            "producer": _producer(),
            "correlation": _correlation(payload),
        }

    def closed(payload: dict[str, object]) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "tenant_context": payload["tenant_context"],
            "operation_id": payload["operation_id"],
            "accounting_period_id": payload["accounting_period_id"],
            "outcome": "CLOSED",
            "issues": [],
            "closed_at": datetime.now(UTC).isoformat(),
            "producer": _producer(),
            "correlation": _correlation(payload),
        }

    @app.post("/v1/period-closes")
    async def close_period(
        request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, object]:
        payload = await body(request, authorization)
        operation_id = str(payload["operation_id"])
        closes.setdefault(operation_id, closed(payload))
        return closes[operation_id]

    @app.post("/v1/period-close-status")
    async def close_status(
        request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, object]:
        payload = await body(request, authorization)
        result = closes.get(str(payload["operation_id"]))
        if result is None:
            raise HTTPException(404, "operation not found")
        return result

    @app.post("/v1/financial-statements")
    async def statement(
        request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, object]:
        payload = await body(request, authorization)
        statement_type = str(payload["statement_type"])
        posted_id = str(stable_id("nova:demo:posted:fallback"))
        if postings:
            posting = next(iter(postings.values()))
            references = posting.get("ledger_references")
            if isinstance(references, list) and references and isinstance(references[0], dict):
                posted_id = str(references[0]["resource_id"])
        values = {
            "TRIAL_BALANCE": [
                ("cash", "1100", "Cash", "-1250.00"),
                ("office_expense", "6100", "Office expense", "1250.00"),
            ],
            "PROFIT_AND_LOSS": [("office_expense", "6100", "Office expense", "1250.00")],
            "BALANCE_SHEET": [
                ("cash", "1100", "Cash", "-1250.00"),
                ("payables", "2100", "Trade payables", "-1250.00"),
            ],
        }
        return {
            "schema_version": "1.0",
            "snapshot_id": str(stable_id(f"nova:demo:snapshot:{statement_type}")),
            "tenant_context": payload["tenant_context"],
            "accounting_period_id": payload["accounting_period_id"],
            "statement_type": statement_type,
            "currency": "INR",
            "as_of": datetime.now(UTC).isoformat(),
            "status": "AVAILABLE",
            "lines": [
                {
                    "line_id": key,
                    "account_reference": account,
                    "label": label,
                    "amount": {"amount": amount, "currency": "INR"},
                    "ledger_references": [
                        {
                            "resource_type": "posted_journal",
                            "resource_id": posted_id,
                            "resource_version": "1",
                        }
                    ],
                }
                for key, account, label, amount in values[statement_type]
            ],
            "producer": _producer(),
            "correlation": _correlation(payload),
        }

    @app.get("/v1/demo/metrics")
    async def demo_metrics(authorization: str | None = Header(default=None)) -> dict[str, int]:
        _authenticate(authorization)
        return metrics

    return app


app = create_demo_role2_app()
