from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from time import monotonic
from uuid import UUID, uuid5

import pytest
from pydantic import ValidationError

from ledgerai_backend.integration.adapters import ReconciliationResult
from ledgerai_backend.reconciliation.contracts import (
    InvoiceFact,
    ReconciliationRequest,
    ReconciliationResponse,
    VersionedBankTransaction,
)
from ledgerai_backend.reconciliation.engine import ReconciliationEngine, ReconciliationInputError
from ledgerai_contracts.v1.common import (
    CorrelationMetadata,
    Money,
    PositiveMoney,
    ProvenanceReference,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_contracts.v1.transactions import BankTransaction, Counterparty

NAMESPACE = UUID("a5e09e42-f89e-4c93-af43-e16a057199d0")
TENANT = EntityTenantContext(
    tenant_id=uuid5(NAMESPACE, "tenant"),
    organization_id=uuid5(NAMESPACE, "organization"),
    legal_entity_id=uuid5(NAMESPACE, "entity"),
)
STARTED = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)


def identifier(label: str) -> UUID:
    return uuid5(NAMESPACE, label)


def evidence(label: str) -> ProvenanceReference:
    return ProvenanceReference(
        source_document_id=identifier(f"document:{label}"),
        document_version="1",
        source_field="total",
        evidence_hash=(label.encode().hex() + "0" * 64)[:64],
    )


def invoice(
    label: str,
    amount: str = "1250.00",
    *,
    currency: str = "INR",
    reference: str | None = "NOVA-PAY-001",
    party: str | None = "Synthetic Office Supplies",
    invoice_date: date = date(2026, 9, 15),
    fingerprint: str | None = None,
    evidence_complete: bool = True,
    tenant: EntityTenantContext = TENANT,
) -> InvoiceFact:
    return InvoiceFact(
        extraction_id=identifier(f"extraction:{label}"),
        extraction_version="1",
        document_id=identifier(f"document:{label}"),
        document_version="1",
        tenant_context=tenant,
        amount=Money(amount=Decimal(amount), currency=currency),
        invoice_date=invoice_date,
        expected_transaction_direction="DEBIT",
        reference=reference,
        party_name=party,
        evidence_complete=evidence_complete,
        content_fingerprint=fingerprint or (label.encode().hex() + "1" * 64)[:64],
        provenance=[evidence(label)],
    )


def transaction(
    label: str,
    amount: str = "1250.00",
    *,
    currency: str = "INR",
    reference: str | None = "NOVA-PAY-001",
    party: str | None = "SYNTHETIC OFFICE SUPPLIES",
    booking_date: date = date(2026, 9, 15),
    fingerprint: str | None = None,
    tenant: EntityTenantContext = TENANT,
) -> VersionedBankTransaction:
    transaction_id = identifier(f"transaction:{label}")
    return VersionedBankTransaction(
        transaction_version="1",
        transaction=BankTransaction(
            schema_version="1.0",
            transaction_id=transaction_id,
            tenant_context=tenant,
            bank_account_id=identifier("bank-account"),
            import_batch_id=identifier("batch"),
            source_row_number=1,
            booking_date=booking_date,
            value_date=booking_date,
            money=PositiveMoney(amount=Decimal(amount), currency=currency),
            direction="DEBIT",
            narration="Synthetic fixture",
            reference=reference,
            counterparty=Counterparty(display_name=party),
            external_source_id=f"EXT-{label}",
            normalization_status="NORMALIZED",
            provenance=[evidence(f"bank:{label}")],
            content_fingerprint=fingerprint or (label.encode().hex() + "2" * 64)[:64],
            correlation=CorrelationMetadata(
                request_id=identifier("bank-request"),
                correlation_id=identifier("correlation"),
            ),
        ),
    )


def request(
    invoices: list[InvoiceFact],
    transactions: list[VersionedBankTransaction],
    *,
    operation: str = "operation",
) -> ReconciliationRequest:
    return ReconciliationRequest(
        schema_version="1.0",
        tenant_context=TENANT,
        operation_id=identifier(operation),
        correlation_id=identifier("correlation"),
        operation_started_at=STARTED,
        strategy_version="reconciliation-rules/1.0.0",
        invoices=invoices,
        transactions=transactions,
    )


def exception_types(result: ReconciliationResponse) -> set[str]:
    return {item.exception_type for item in result.exceptions}


def test_exact_match_is_deterministic_and_role4_compatible() -> None:
    operation = request([invoice("exact")], [transaction("exact")])
    first = ReconciliationEngine().reconcile(operation)
    second = ReconciliationEngine().reconcile(operation)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.proposal.match_type == "ONE_TO_ONE"
    assert first.proposal.status == "PROPOSED"
    assert first.proposal.score == Decimal("1.000")
    assert all(record.resource_version == "1" for record in first.proposal.records)
    assert first.proposal.operation_id == operation.operation_id
    ReconciliationResult.model_validate(first.model_dump(mode="json"))


@pytest.mark.parametrize("difference", [Decimal("0.00"), Decimal("0.01")])
def test_amount_tolerance_is_inclusive(difference: Decimal) -> None:
    result = ReconciliationEngine().reconcile(
        request(
            [invoice("amount-boundary")],
            [transaction("amount-boundary", str(Decimal("1250.00") + difference))],
        )
    )
    assert result.proposal.match_type == "ONE_TO_ONE"


def test_date_window_boundary_is_inclusive() -> None:
    result = ReconciliationEngine().reconcile(
        request(
            [invoice("date-boundary")],
            [transaction("date-boundary", booking_date=date(2026, 9, 22))],
        )
    )
    assert result.proposal.match_type == "ONE_TO_ONE"


def test_duplicate_invoice_and_bank_row_are_blocking() -> None:
    duplicate_invoice_fingerprint = "a" * 64
    duplicate_transaction_fingerprint = "b" * 64
    result = ReconciliationEngine().reconcile(
        request(
            [
                invoice("duplicate-invoice-a", fingerprint=duplicate_invoice_fingerprint),
                invoice("duplicate-invoice-b", fingerprint=duplicate_invoice_fingerprint),
            ],
            [
                transaction("duplicate-row-a", fingerprint=duplicate_transaction_fingerprint),
                transaction("duplicate-row-b", fingerprint=duplicate_transaction_fingerprint),
            ],
        )
    )
    assert {"DUPLICATE_DOCUMENT", "DUPLICATE_TRANSACTION"} <= exception_types(result)
    assert all(item.blocks_posting for item in result.exceptions)


def test_combined_payment_is_one_to_many() -> None:
    result = ReconciliationEngine().reconcile(
        request(
            [invoice("combined-a", "700.00"), invoice("combined-b", "550.00")],
            [transaction("combined", "1250.00")],
        )
    )
    assert result.proposal.match_type == "ONE_TO_MANY"
    assert len(result.proposal.records) == 3


def test_split_payment_is_many_to_one() -> None:
    result = ReconciliationEngine().reconcile(
        request(
            [invoice("split", "1250.00")],
            [transaction("split-a", "700.00"), transaction("split-b", "550.00")],
        )
    )
    assert result.proposal.match_type == "MANY_TO_ONE"
    assert len(result.proposal.records) == 3


def test_partial_payment_requires_review_and_amount_exception() -> None:
    result = ReconciliationEngine().reconcile(
        request([invoice("partial")], [transaction("partial", "1000.00")])
    )
    assert result.proposal.match_type == "PARTIAL"
    assert result.proposal.status == "REVIEW_REQUIRED"
    assert "AMOUNT_MISMATCH" in exception_types(result)


def test_currency_conflict_never_matches() -> None:
    result = ReconciliationEngine().reconcile(
        request([invoice("currency")], [transaction("currency", currency="USD")])
    )
    assert result.proposal.match_type == "UNMATCHED"
    assert "CURRENCY_MISMATCH" in exception_types(result)


def test_missing_evidence_is_explicit() -> None:
    result = ReconciliationEngine().reconcile(
        request([invoice("missing", evidence_complete=False)], [transaction("missing")])
    )
    assert "MISSING_EVIDENCE" in exception_types(result)


def test_ambiguous_candidates_require_review() -> None:
    result = ReconciliationEngine().reconcile(
        request(
            [invoice("ambiguous-a"), invoice("ambiguous-b")],
            [transaction("ambiguous")],
        )
    )
    assert result.proposal.status == "REVIEW_REQUIRED"
    assert "AMBIGUOUS_CANDIDATES" in exception_types(result)


def test_no_candidates_produces_unmatched_exceptions() -> None:
    result = ReconciliationEngine().reconcile(
        request(
            [invoice("none", reference="INVOICE-X", invoice_date=date(2026, 1, 1))],
            [transaction("none", "25.00", reference="PAYMENT-Y")],
        )
    )
    assert result.proposal.match_type == "UNMATCHED"
    assert {"UNMATCHED_INVOICE", "UNMATCHED_TRANSACTION"} <= exception_types(result)


def test_foreign_tenant_and_out_of_order_versions_are_rejected() -> None:
    foreign = TENANT.model_copy(update={"legal_entity_id": identifier("foreign-entity")})
    with pytest.raises(ValidationError, match="foreign-tenant or mixed-entity"):
        request([invoice("foreign", tenant=foreign)], [transaction("foreign")])

    duplicate = invoice("version")
    newer = duplicate.model_copy(update={"extraction_version": "2"})
    with pytest.raises(ValidationError, match="out-of-order invoice versions"):
        request([duplicate, newer], [])


def test_malformed_model_derived_money_is_rejected() -> None:
    raw = invoice("malformed").model_dump(mode="json")
    raw["amount"]["amount"] = 1250.0
    with pytest.raises(ValidationError, match="decimal string"):
        InvoiceFact.model_validate(raw)


def test_candidate_cross_product_is_rejected_before_matching() -> None:
    invoices = [invoice(f"large-invoice-{index}") for index in range(101)]
    transactions = [transaction(f"large-transaction-{index}") for index in range(100)]
    started = monotonic()
    with pytest.raises(ReconciliationInputError, match="cross-product"):
        ReconciliationEngine().reconcile(request(invoices, transactions))
    assert monotonic() - started < 0.25


def test_nova_planted_fifty_rupee_mismatch() -> None:
    result = ReconciliationEngine().reconcile(
        request(
            [invoice("nova", "1250.00", reference="NOVA-DEMO-PAY-001")],
            [
                transaction("nova-payment", "1250.00", reference="NOVA-DEMO-PAY-001"),
                transaction(
                    "nova-planted",
                    "50.00",
                    reference="NOVA-DEMO-ISSUE-001",
                    party="SYNTHETIC REVIEW VENDOR",
                    booking_date=date(2026, 9, 16),
                ),
            ],
            operation="nova-operation",
        )
    )
    mismatch = [item for item in result.exceptions if item.exception_type == "AMOUNT_MISMATCH"]
    assert result.proposal.match_type == "ONE_TO_ONE"
    assert mismatch
    assert "BATCH_AMOUNT_MISMATCH" in mismatch[0].reason_codes
    assert mismatch[0].blocks_posting is True
    assert mismatch[0].blocks_close is True


def test_repeated_order_permutations_keep_same_candidate_ranking() -> None:
    invoices = [invoice(f"property-{index}", str(100 + index)) for index in range(5)]
    transactions = [transaction(f"property-{index}", str(100 + index)) for index in range(5)]
    forward = ReconciliationEngine().reconcile(request(invoices, transactions))
    reverse = ReconciliationEngine().reconcile(
        request(list(reversed(invoices)), list(reversed(transactions)))
    )
    assert forward.proposal.proposal_id == reverse.proposal.proposal_id
    assert forward.proposal.candidate_scores == reverse.proposal.candidate_scores


def test_date_outside_window_is_not_eligible() -> None:
    result = ReconciliationEngine().reconcile(
        request(
            [invoice("outside-date")],
            [transaction("outside-date", booking_date=date(2026, 9, 15) + timedelta(days=8))],
        )
    )
    assert result.proposal.match_type == "UNMATCHED"
