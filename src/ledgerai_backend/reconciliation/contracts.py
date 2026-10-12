"""Strict request and response contracts for the Role 3 boundary."""

from __future__ import annotations

from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from ledgerai_contracts.v1.common import (
    ContractModel,
    Money,
    ProvenanceReference,
    SchemaVersion,
    UtcDateTime,
    VersionToken,
)
from ledgerai_contracts.v1.exceptions import ExceptionRecord
from ledgerai_contracts.v1.reconciliation import MatchProposal
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_contracts.v1.transactions import BankTransaction


class InvoiceFact(ContractModel):
    """Role 1 facts reduced to the immutable evidence needed for matching."""

    extraction_id: UUID
    extraction_version: VersionToken
    document_id: UUID
    document_version: VersionToken
    tenant_context: EntityTenantContext
    amount: Money
    invoice_date: date
    expected_transaction_direction: Literal["DEBIT", "CREDIT"]
    reference: str | None = Field(default=None, min_length=1, max_length=128)
    party_name: str | None = Field(default=None, min_length=1, max_length=256)
    evidence_complete: bool
    content_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    provenance: list[ProvenanceReference] = Field(default_factory=list, max_length=50)


class VersionedBankTransaction(ContractModel):
    transaction_version: VersionToken
    transaction: BankTransaction


class ReconciliationRequest(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    operation_id: UUID
    correlation_id: UUID
    causation_id: UUID | None = None
    operation_started_at: UtcDateTime
    strategy_version: Literal["reconciliation-rules/1.0.0"]
    invoices: list[InvoiceFact] = Field(default_factory=list, max_length=500)
    transactions: list[VersionedBankTransaction] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_scope_and_versions(self) -> Self:
        if not self.invoices and not self.transactions:
            raise ValueError("at least one invoice or transaction is required")
        contexts = [invoice.tenant_context for invoice in self.invoices]
        contexts.extend(item.transaction.tenant_context for item in self.transactions)
        if any(context != self.tenant_context for context in contexts):
            raise ValueError("foreign-tenant or mixed-entity input is not allowed")
        invoice_versions: dict[UUID, str] = {}
        for invoice in self.invoices:
            previous = invoice_versions.setdefault(
                invoice.extraction_id, invoice.extraction_version
            )
            if previous != invoice.extraction_version:
                raise ValueError("conflicting or out-of-order invoice versions")
        transaction_versions: dict[UUID, str] = {}
        for item in self.transactions:
            transaction_id = item.transaction.transaction_id
            previous = transaction_versions.setdefault(transaction_id, item.transaction_version)
            if previous != item.transaction_version:
                raise ValueError("conflicting or out-of-order transaction versions")
        return self


class ReconciliationResponse(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    proposal: MatchProposal
    exceptions: list[ExceptionRecord] = Field(default_factory=list, max_length=100)
