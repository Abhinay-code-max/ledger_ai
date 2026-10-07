"""Human approval decisions bound to an exact resource version."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ledgerai_contracts.v1.common import (
    ActorReference,
    ContractModel,
    CorrelationMetadata,
    SchemaVersion,
    UtcDateTime,
    VersionedResourceReference,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class ApprovalDecision(ContractModel):
    schema_version: SchemaVersion
    decision_id: UUID
    tenant_context: EntityTenantContext
    approval_request_id: UUID
    reviewed_resource: VersionedResourceReference
    actor: ActorReference
    action: Literal["APPROVE", "CORRECT", "REJECT", "REQUEST_EVIDENCE", "ESCALATE"]
    reason: str | None = None
    structured_corrections: dict[str, Any] | None = None
    authorization_roles: list[str] = Field(min_length=1)
    separation_of_duties_checked: bool
    separation_of_duties_rule: str | None = None
    decided_at: UtcDateTime
    correlation: CorrelationMetadata

    @model_validator(mode="after")
    def corrections_require_new_content(self) -> ApprovalDecision:
        if self.action == "CORRECT" and not self.structured_corrections:
            raise ValueError("CORRECT requires structured_corrections for a new proposal version")
        return self
