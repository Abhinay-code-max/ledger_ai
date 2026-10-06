"""Normalized bank transaction contract."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field

from ledgerai_contracts.v1.common import (
    ContractModel,
    CorrelationMetadata,
    PositiveMoney,
    ProvenanceReference,
    SchemaVersion,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class Counterparty(ContractModel):
    display_name: str | None = None
    masked_account_reference: str | None = None


class BankTransaction(ContractModel):
    schema_version: SchemaVersion
    transaction_id: UUID
    tenant_context: EntityTenantContext
    bank_account_id: UUID
    import_batch_id: UUID
    source_row_number: int = Field(ge=1)
    booking_date: date
    value_date: date | None = None
    money: PositiveMoney
    direction: Literal["DEBIT", "CREDIT"]
    narration: str = ""
    reference: str | None = None
    counterparty: Counterparty | None = None
    external_source_id: str | None = None
    normalization_status: Literal["NORMALIZED", "REVIEW_REQUIRED", "REJECTED"]
    provenance: list[ProvenanceReference]
    content_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    correlation: CorrelationMetadata
