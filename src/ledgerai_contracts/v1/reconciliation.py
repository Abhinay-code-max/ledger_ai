"""Reconciliation proposals are evidence, never final decisions."""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from ledgerai_contracts.v1.common import (
    Confidence,
    ContractModel,
    CorrelationMetadata,
    ProducerMetadata,
    ProvenanceReference,
    ResourceReference,
    SchemaVersion,
    UtcDateTime,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class MatchReason(ContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    explanation: str = Field(min_length=1)
    contribution: Decimal | None = Field(default=None, ge=Decimal("-1"), le=Decimal("1"))


class MatchConflict(ContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    explanation: str = Field(min_length=1)


class MatchProposal(ContractModel):
    schema_version: SchemaVersion
    proposal_id: UUID
    proposal_version: int = Field(ge=1)
    tenant_context: EntityTenantContext
    records: list[ResourceReference] = Field(min_length=1)
    match_type: Literal["ONE_TO_ONE", "MANY_TO_ONE", "ONE_TO_MANY", "PARTIAL", "UNMATCHED"]
    confidence: Confidence
    score: Decimal | None = None
    reasons: list[MatchReason] = Field(min_length=1)
    conflicts: list[MatchConflict] = Field(default_factory=list)
    producer: ProducerMetadata
    status: Literal["PROPOSED", "REVIEW_REQUIRED", "ACCEPTED", "REJECTED", "SUPERSEDED"]
    created_at: UtcDateTime
    updated_at: UtcDateTime
    correlation: CorrelationMetadata
    provenance: list[ProvenanceReference] = Field(default_factory=list)
