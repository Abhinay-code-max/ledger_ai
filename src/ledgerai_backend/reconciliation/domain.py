"""Internal domain models and canonical v1 wire translators for Role 3."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from ledgerai_backend.reconciliation.contracts import ReconciliationResponse
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
from ledgerai_contracts.v1.exceptions import ExceptionRecord
from ledgerai_contracts.v1.reconciliation import (
    MatchConflict,
    MatchProposal,
    MatchReason,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class ConfidenceComponent(ContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    value: Confidence
    weight: Confidence
    explanation: str = Field(min_length=1, max_length=500)


class CandidateScore(ContractModel):
    records: list[ResourceReference] = Field(min_length=2, max_length=6)
    score: Confidence
    eligible: bool
    components: list[ConfidenceComponent] = Field(min_length=1, max_length=10)
    conflicts: list[MatchConflict] = Field(default_factory=list, max_length=20)


class InternalMatchProposal(ContractModel):
    schema_version: SchemaVersion
    proposal_id: UUID
    proposal_version: int = Field(ge=1)
    tenant_context: EntityTenantContext
    operation_id: UUID
    records: list[ResourceReference] = Field(min_length=1, max_length=6)
    match_type: Literal["ONE_TO_ONE", "MANY_TO_ONE", "ONE_TO_MANY", "PARTIAL", "UNMATCHED"]
    confidence: Confidence
    score: Decimal | None = None
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


class InternalExceptionRecord(ContractModel):
    schema_version: SchemaVersion
    exception_id: UUID
    tenant_context: EntityTenantContext
    exception_type: str = Field(min_length=1)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    operation_id: UUID
    involved_resources: list[ResourceReference] = Field(min_length=1, max_length=20)
    explanation: str = Field(min_length=1, max_length=1000)
    reason_codes: list[str] = Field(min_length=1, max_length=20)
    supporting_evidence: list[ProvenanceReference] = Field(default_factory=list, max_length=100)
    suggested_action: str | None = None
    required_action: str | None = None
    resolution_status: Literal["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"]
    resolution_reference: ResourceReference | None = None
    blocks_posting: bool
    blocks_close: bool
    algorithm_version: str = Field(min_length=1, max_length=128)
    rule_version: str = Field(min_length=1, max_length=128)
    detector: ProducerMetadata
    created_at: UtcDateTime
    updated_at: UtcDateTime
    correlation: CorrelationMetadata


class InternalReconciliationResult(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    proposal: InternalMatchProposal
    exceptions: list[InternalExceptionRecord] = Field(default_factory=list, max_length=100)


def to_canonical_proposal(internal: InternalMatchProposal) -> MatchProposal:
    """Map internal domain proposal into frozen canonical v1 wire contract."""
    return MatchProposal(
        schema_version="1.0",
        proposal_id=internal.proposal_id,
        proposal_version=internal.proposal_version,
        tenant_context=internal.tenant_context,
        records=internal.records,
        match_type=internal.match_type,
        confidence=internal.confidence,
        score=internal.score,
        reasons=internal.reasons,
        conflicts=internal.conflicts,
        producer=internal.producer,
        status=internal.status,
        created_at=internal.created_at,
        updated_at=internal.updated_at,
        correlation=internal.correlation,
        provenance=internal.provenance,
    )


def to_canonical_exception(internal: InternalExceptionRecord) -> ExceptionRecord:
    """Map internal domain exception into frozen canonical v1 wire contract."""
    return ExceptionRecord(
        schema_version="1.0",
        exception_id=internal.exception_id,
        tenant_context=internal.tenant_context,
        exception_type=internal.exception_type,
        severity=internal.severity,
        involved_resources=internal.involved_resources,
        explanation=internal.explanation,
        reason_codes=internal.reason_codes,
        supporting_evidence=internal.supporting_evidence,
        suggested_action=internal.suggested_action,
        required_action=internal.required_action,
        resolution_status=internal.resolution_status,
        resolution_reference=internal.resolution_reference,
        detector=internal.detector,
        created_at=internal.created_at,
        updated_at=internal.updated_at,
        correlation=internal.correlation,
    )


def to_canonical_response(internal: InternalReconciliationResult) -> ReconciliationResponse:
    """Map internal reconciliation result into frozen canonical v1 wire response."""
    return ReconciliationResponse(
        schema_version="1.0",
        tenant_context=internal.tenant_context,
        proposal=to_canonical_proposal(internal.proposal),
        exceptions=[to_canonical_exception(exc) for exc in internal.exceptions],
    )
