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
    SchemaVersion,
    UtcDateTime,
    VersionedResourceReference,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class MatchReason(ContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    explanation: str = Field(min_length=1)
    contribution: Decimal | None = Field(default=None, ge=Decimal("-1"), le=Decimal("1"))


class MatchConflict(ContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    explanation: str = Field(min_length=1)


class ConfidenceComponent(ContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    value: Confidence
    weight: Confidence
    explanation: str = Field(min_length=1, max_length=500)


class CandidateScore(ContractModel):
    records: list[VersionedResourceReference] = Field(min_length=2, max_length=6)
    score: Confidence
    eligible: bool
    components: list[ConfidenceComponent] = Field(min_length=1, max_length=10)
    conflicts: list[MatchConflict] = Field(default_factory=list, max_length=20)


class MatchProposal(ContractModel):
    schema_version: SchemaVersion
    proposal_id: UUID
    proposal_version: int = Field(ge=1)
    tenant_context: EntityTenantContext
    operation_id: UUID
    records: list[VersionedResourceReference] = Field(min_length=1, max_length=6)
    match_type: Literal["ONE_TO_ONE", "MANY_TO_ONE", "ONE_TO_MANY", "PARTIAL", "UNMATCHED"]
    confidence: Confidence
    score: Confidence | None = None
    strategy_version: str = Field(min_length=1, max_length=128)
    algorithm_version: str = Field(min_length=1, max_length=128)
    candidate_scores: list[CandidateScore] = Field(default_factory=list, max_length=100)
    confidence_components: list[ConfidenceComponent] = Field(min_length=1, max_length=10)
    reasons: list[MatchReason] = Field(min_length=1, max_length=20)
    conflicts: list[MatchConflict] = Field(default_factory=list, max_length=20)
    producer: ProducerMetadata
    status: Literal["PROPOSED", "REVIEW_REQUIRED", "ACCEPTED", "REJECTED", "SUPERSEDED"]
    created_at: UtcDateTime
    updated_at: UtcDateTime
    correlation: CorrelationMetadata
    provenance: list[ProvenanceReference] = Field(default_factory=list, max_length=100)
