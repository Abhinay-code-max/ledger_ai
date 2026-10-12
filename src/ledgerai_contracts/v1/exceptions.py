"""Detected exception contract."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from ledgerai_contracts.v1.common import (
    ContractModel,
    CorrelationMetadata,
    ProducerMetadata,
    ProvenanceReference,
    ResourceReference,
    SchemaVersion,
    UtcDateTime,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class ExceptionRecord(ContractModel):
    schema_version: SchemaVersion
    exception_id: UUID
    tenant_context: EntityTenantContext
    exception_type: str = Field(min_length=1)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    involved_resources: list[ResourceReference] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    reason_codes: list[str] = Field(min_length=1)
    supporting_evidence: list[ProvenanceReference] = Field(default_factory=list)
    suggested_action: str | None = None
    required_action: str | None = None
    resolution_status: Literal["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"]
    resolution_reference: ResourceReference | None = None
    detector: ProducerMetadata
    created_at: UtcDateTime
    updated_at: UtcDateTime
    correlation: CorrelationMetadata
