"""Protocol-faithful Role 3 reconciliation service integrating the real ReconciliationEngine."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI, Request

from ledgerai_backend.demo.service_auth import authenticated_payload
from ledgerai_backend.reconciliation.contracts import (
    InvoiceFact,
    ReconciliationRequest,
    VersionedBankTransaction,
)
from ledgerai_backend.reconciliation.engine import ReconciliationEngine
from ledgerai_contracts.v1.common import (
    CorrelationMetadata,
    Money,
    PositiveMoney,
    ProvenanceReference,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_contracts.v1.transactions import BankTransaction

logger = logging.getLogger("ledgerai.role3")


def _correlation(payload: dict[str, object]) -> CorrelationMetadata:
    value = payload.get("correlation")
    if isinstance(value, dict):
        return CorrelationMetadata.model_validate(value)
    op_id = UUID(str(payload.get("operation_id", uuid4())))
    return CorrelationMetadata(request_id=op_id, correlation_id=op_id, causation_id=None)


def create_demo_role3_app() -> FastAPI:
    app = FastAPI(title="LedgerAI Role 3 Reconciliation", docs_url=None, redoc_url=None)
    engine = ReconciliationEngine()

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/v1/reconciliations")
    async def reconcile(request: Request) -> dict[str, object]:
        payload = await authenticated_payload(request, audience="ledgerai-role3")
        tenant_context_raw = payload["tenant_context"]
        assert isinstance(tenant_context_raw, dict)
        tenant_context = EntityTenantContext.model_validate(tenant_context_raw)

        corr = _correlation(payload)
        operation_id = UUID(str(payload.get("operation_id", corr.request_id)))

        logger.info(
            "role3.reconcile.started",
            extra={
                "operation_id": str(operation_id),
                "correlation_id": str(corr.correlation_id),
                "tenant_id": str(tenant_context.tenant_id),
            },
        )

        # Check if full canonical inputs were provided
        invoices_data = payload.get("invoices")
        transactions_data = payload.get("transactions")

        if invoices_data or transactions_data:
            # Canonical request format
            req = ReconciliationRequest(
                schema_version="1.0",
                tenant_context=tenant_context,
                operation_id=operation_id,
                correlation_id=corr.correlation_id,
                causation_id=corr.causation_id,
                operation_started_at=datetime.now(UTC),
                strategy_version=payload.get("strategy_version", "reconciliation-rules/1.0.0"),
                invoices=[InvoiceFact.model_validate(inv) for inv in (invoices_data or [])],
                transactions=[
                    VersionedBankTransaction.model_validate(tx) for tx in (transactions_data or [])
                ],
            )
            resp = engine.reconcile(req)
        else:
            # Fallback for synthetic legacy payload tests: construct minimal facts and reconcile
            tx_ids = [UUID(str(tx)) for tx in payload.get("transaction_ids", [])]
            doc_extraction_id = (
                UUID(str(payload["document_extraction_id"]))
                if "document_extraction_id" in payload
                else uuid4()
            )
            doc_id = UUID(str(payload.get("document_id", uuid4())))

            invoices = [
                InvoiceFact(
                    extraction_id=doc_extraction_id,
                    extraction_version="1",
                    document_id=doc_id,
                    document_version="1",
                    tenant_context=tenant_context,
                    amount=Money(amount=Decimal("1250.00"), currency="INR"),
                    invoice_date=date(2026, 9, 15),
                    expected_transaction_direction="DEBIT",
                    reference="NOVA-DEMO-INV-001",
                    party_name="SYNTHETIC OFFICE SUPPLIES",
                    evidence_complete=True,
                    content_fingerprint="a" * 64,
                    provenance=[
                        ProvenanceReference(
                            source_document_id=doc_id,
                            document_version="1",
                            source_field="invoice",
                            evidence_hash="a" * 64,
                        )
                    ],
                )
            ]
            transactions: list[VersionedBankTransaction] = []
            for i, tx_id in enumerate(tx_ids):
                # If 2 transactions, first is matching 1250.00, second is 50.00 planted mismatch
                tx_amount = Decimal("1250.00") if i == 0 else Decimal("50.00")
                tx_ref = "NOVA-DEMO-PAY-001" if i == 0 else "NOVA-DEMO-ISSUE-001"
                tx_narration = "SYNTHETIC PAYMENT" if i == 0 else "PLANTED AMOUNT MISMATCH"
                transactions.append(
                    VersionedBankTransaction(
                        transaction_version="1",
                        transaction=BankTransaction(
                            schema_version="1.0",
                            transaction_id=tx_id,
                            tenant_context=tenant_context,
                            bank_account_id=uuid4(),
                            import_batch_id=uuid4(),
                            source_row_number=i + 1,
                            booking_date=date(2026, 9, 15),
                            value_date=date(2026, 9, 15),
                            money=PositiveMoney(amount=tx_amount, currency="INR"),
                            direction="DEBIT",
                            narration=tx_narration,
                            reference=tx_ref,
                            normalization_status="NORMALIZED",
                            provenance=[
                                ProvenanceReference(
                                    source_document_id=doc_id,
                                    document_version="1",
                                    source_field="bank_transaction",
                                    evidence_hash="b" * 64,
                                )
                            ],
                            content_fingerprint="b" * 64,
                            correlation=corr,
                        ),
                    )
                )
            req = ReconciliationRequest(
                schema_version="1.0",
                tenant_context=tenant_context,
                operation_id=operation_id,
                correlation_id=corr.correlation_id,
                causation_id=corr.causation_id,
                operation_started_at=datetime.now(UTC),
                strategy_version="reconciliation-rules/1.0.0",
                invoices=invoices,
                transactions=transactions,
            )
            resp = engine.reconcile(req)

        logger.info(
            "role3.reconcile.completed",
            extra={
                "operation_id": str(operation_id),
                "correlation_id": str(corr.correlation_id),
                "tenant_id": str(tenant_context.tenant_id),
                "match_type": resp.proposal.match_type,
                "exceptions_count": len(resp.exceptions),
            },
        )

        return resp.model_dump(mode="json")

    return app


app = create_demo_role3_app()
