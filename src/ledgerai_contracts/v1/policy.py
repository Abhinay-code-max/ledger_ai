"""Reproducible versioned policy decisions."""

from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from ledgerai_contracts.v1.common import (
    ContractModel,
    CorrelationMetadata,
    ResourceReference,
    SchemaVersion,
    UtcDateTime,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class PolicyDecision(ContractModel):
    schema_version: SchemaVersion
    decision_id: UUID
    tenant_context: EntityTenantContext
    subject: ResourceReference
    policy_set_id: UUID
    policy_set_version: str = Field(min_length=1)
    outcome: Literal["AUTO_ELIGIBLE", "REVIEW_REQUIRED", "ESCALATED", "BLOCKED"]
    evaluated_inputs: dict[str, Any]
    matched_rule_ids: list[str]
    reason_codes: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    evaluator_version: str = Field(min_length=1)
    decided_at: UtcDateTime
    correlation: CorrelationMetadata
