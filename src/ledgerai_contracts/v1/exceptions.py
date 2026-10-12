"""Detected exception contract."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from ledgerai_contracts.v1.common import (
    ContractModel,
    CorrelationMetadata,
    ProducerMetadata,
    ProvenanceReference,
    SchemaVersion,
    UtcDateTime,
    VersionedResourceReference,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class ExceptionRecord(ContractModel):
    schema_version: SchemaVersion
    exception_id: UUID
    tenant_context: EntityTenantContext
    exception_type: str = Field(min_length=1)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    operation_id: UUID
    involved_resources: list[VersionedResourceReference] = Field(min_length=1, max_length=20)
    explanation: str = Field(min_length=1, max_length=1000)
    reason_codes: list[str] = Field(min_length=1, max_length=20)
    supporting_evidence: list[ProvenanceReference] = Field(default_factory=list, max_length=100)
    suggested_action: str | None = None
    required_action: str | None = None
    resolution_status: Literal["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"]
    resolution_reference: VersionedResourceReference | None = None
    blocks_posting: bool
    blocks_close: bool
    algorithm_version: str = Field(min_length=1, max_length=128)
    rule_version: str = Field(min_length=1, max_length=128)
    detector: ProducerMetadata
    created_at: UtcDateTime
    updated_at: UtcDateTime
    correlation: CorrelationMetadata
