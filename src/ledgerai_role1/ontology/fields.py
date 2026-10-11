"""Canonical, versioned field and document types for Role 1 Document Intelligence."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

ONTOLOGY_VERSION: Final[str] = "1.0.0"


class DocumentType(StrEnum):
    """Document classification within Role 1 NOVA vertical slice."""

    SUPPLIER_INVOICE = "SUPPLIER_INVOICE"
    CUSTOMER_INVOICE = "CUSTOMER_INVOICE"
    RECEIPT = "RECEIPT"
    BANK_STATEMENT = "BANK_STATEMENT"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    UNKNOWN = "UNKNOWN"

    def to_contract_classification(self) -> str:
        """Map fine-grained Role 1 document type to cross-role contract classification."""
        if self in {
            DocumentType.SUPPLIER_INVOICE,
            DocumentType.CUSTOMER_INVOICE,
            DocumentType.PURCHASE_ORDER,
        }:
            return "INVOICE"
        if self == DocumentType.RECEIPT:
            return "RECEIPT"
        if self == DocumentType.BANK_STATEMENT:
            return "BANK_STATEMENT"
        return "UNKNOWN"


class CanonicalFieldName(StrEnum):
    """Canonical ontology field names for extraction."""

    DOCUMENT_TYPE = "document_type"
    DOCUMENT_NUMBER = "document_number"
    INVOICE_NUMBER = "invoice_number"
    ISSUE_DATE = "issue_date"
    INVOICE_DATE = "invoice_date"
    DUE_DATE = "due_date"
    SUPPLIER_NAME = "supplier_name"
    CUSTOMER_NAME = "customer_name"
    SUPPLIER_TAX_ID = "supplier_tax_id"
    CUSTOMER_TAX_ID = "customer_tax_id"
    PURCHASE_ORDER_REFERENCE = "purchase_order_reference"
    SUBTOTAL = "subtotal"
    TAX_AMOUNT = "tax"
    TOTAL_AMOUNT = "total"
    CURRENCY = "currency"
    BANK_ACCOUNT_REFERENCE = "bank_account_reference"


CRITICAL_FIELDS_BY_DOC_TYPE: Final[dict[DocumentType, frozenset[str]]] = {
    DocumentType.SUPPLIER_INVOICE: frozenset(
        {"supplier_name", "invoice_number", "invoice_date", "total"}
    ),
    DocumentType.CUSTOMER_INVOICE: frozenset(
        {"customer_name", "invoice_number", "invoice_date", "total"}
    ),
    DocumentType.RECEIPT: frozenset({"supplier_name", "invoice_date", "total"}),
    DocumentType.BANK_STATEMENT: frozenset({"supplier_name", "invoice_date", "total"}),
    DocumentType.PURCHASE_ORDER: frozenset({"supplier_name", "purchase_order_reference", "total"}),
    DocumentType.UNKNOWN: frozenset(),
}
