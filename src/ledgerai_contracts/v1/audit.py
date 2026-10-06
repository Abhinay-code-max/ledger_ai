"""Minimal, safe audit evidence without sensitive payloads."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from ledgerai_contracts.v1.common import (
    ActorReference,
    ContractModel,
    CorrelationMetadata,
    ProducerMetadata,
    SchemaVersion,
    UtcDateTime,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class AuditEvent(ContractModel):
    schema_version: SchemaVersion
    audit_event_id: UUID
    tenant_context: EntityTenantContext
    actor: ActorReference
    action: str
    resource_type: str
    resource_id: UUID
    resource_version: str | None = None
    before_hash: str | None = None
    after_hash: str | None = None
    correlation: CorrelationMetadata
    producer_versions: list[ProducerMetadata] = Field(default_factory=list)
    schema_versions: list[str] = Field(default_factory=list)
    rule_versions: list[str] = Field(default_factory=list)
    policy_versions: list[str] = Field(default_factory=list)
    outcome: Literal["SUCCEEDED", "FAILED", "DENIED", "PENDING"]
    occurred_at: UtcDateTime
    source_ip: str | None = None
    client_metadata: dict[str, str] | None = None
