"""Tests for ontology schema, arithmetic consistency, and contract conversion."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from ledgerai_contracts.v1.common import CorrelationMetadata
from ledgerai_contracts.v1.documents import FieldState, ReviewDisposition
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role1.ontology.fields import DocumentType
from ledgerai_role1.ontology.schema import (
    AnnotatedLineItem,
    CanonicalDocumentData,
    to_contract_extraction,
)


def test_canonical_document_arithmetic_check() -> None:
    # Valid matching arithmetic
    doc = CanonicalDocumentData(
        document_type=DocumentType.SUPPLIER_INVOICE,
        document_number="INV-101",
        issue_date=date(2026, 1, 1),
        total_amount=Decimal("110.00"),
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("10.00"),
        currency="USD",
    )
    assert not any(i.code == "ARITHMETIC_TOTAL_MISMATCH" for i in doc.validation_issues)

    # Arithmetic mismatch flagged as ERROR validation issue
    mismatched = CanonicalDocumentData(
        document_type=DocumentType.SUPPLIER_INVOICE,
        document_number="INV-102",
        issue_date=date(2026, 1, 1),
        total_amount=Decimal("150.00"),
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("10.00"),
        currency="USD",
    )
    assert any(i.code == "ARITHMETIC_TOTAL_MISMATCH" for i in mismatched.validation_issues)


def test_float_money_rejected() -> None:
    with pytest.raises(ValueError, match="Floating point is forbidden"):
        CanonicalDocumentData(
            document_type=DocumentType.RECEIPT,
            total_amount=12.50,  # type: ignore[arg-type]
            currency="USD",
        )


def test_bank_account_automatic_masking() -> None:
    doc = CanonicalDocumentData(
        document_type=DocumentType.BANK_STATEMENT,
        total_amount=Decimal("500.00"),
        currency="USD",
        bank_account_reference="9876543210",
    )
    assert doc.bank_account_reference == "****3210"


def test_conversion_to_strict_contract() -> None:
    doc = CanonicalDocumentData(
        document_type=DocumentType.SUPPLIER_INVOICE,
        document_number="INV-999",
        issue_date=date(2026, 1, 15),
        supplier_name="Alpha Tech Corp",
        total_amount=Decimal("118.00"),
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("18.00"),
        currency="USD",
        line_items=[
            AnnotatedLineItem(
                line_number=1,
                description="Consulting Services",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                line_amount=Decimal("100.00"),
                currency="USD",
            )
        ],
    )

    tenant = EntityTenantContext(
        tenant_id=uuid4(),
        organization_id=uuid4(),
        legal_entity_id=uuid4(),
    )
    correlation = CorrelationMetadata(
        request_id=uuid4(),
        correlation_id=uuid4(),
    )

    contract = to_contract_extraction(
        doc,
        extraction_id=uuid4(),
        document_id=uuid4(),
        document_version="v1",
        tenant_context=tenant,
        correlation=correlation,
    )

    assert contract.schema_version == "1.0"
    assert contract.classification == "INVOICE"
    assert contract.review_disposition == ReviewDisposition.NOT_REQUIRED
    assert len(contract.fields) > 0
    assert len(contract.line_items) == 1

    # Check total field
    total_f = next(f for f in contract.fields if f.field_name == "total")
    assert total_f.state == FieldState.EXTRACTED
    assert total_f.value.amount == Decimal("118.00")  # type: ignore[union-attr]
    assert total_f.value.currency == "USD"  # type: ignore[union-attr]
