"""Unposted, versioned journal proposals."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from ledgerai_contracts.v1.common import (
    Confidence,
    ContractModel,
    CorrelationMetadata,
    CurrencyCode,
    PositiveMoney,
    ProducerMetadata,
    ProvenanceReference,
    ResourceReference,
    SchemaVersion,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext

AccountingValidation = Annotated[str, StringConstraints(pattern=r"^NOT_VALIDATED$")]


class ProposedJournalLine(ContractModel):
    line_id: UUID
    account_reference: str = Field(min_length=1)
    direction: Literal["DEBIT", "CREDIT"]
    amount: PositiveMoney
    description: str | None = None
    source_evidence: list[ProvenanceReference] = Field(min_length=1)


class JournalProposal(ContractModel):
    schema_version: SchemaVersion
    proposal_id: UUID
    proposal_version: int = Field(ge=1, description="Immutable; edits create a new version")
    tenant_context: EntityTenantContext
    proposed_journal_date: date
    currency: CurrencyCode
    lines: list[ProposedJournalLine] = Field(min_length=2)
    source_evidence: list[ProvenanceReference] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    confidence: Confidence | None = None
    producer: ProducerMetadata
    policy_decision: ResourceReference | None = None
    approval_decision: ResourceReference | None = None
    accounting_validation: AccountingValidation
    posting_status: Literal["UNPOSTED"]
    correlation: CorrelationMetadata
