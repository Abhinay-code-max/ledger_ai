"""Tenant boundary primitives.

Tenant IDs are routing assertions carried by contracts, not trusted client claims. APIs must
derive and verify them from authenticated membership. EntityTenantContext is used whenever a
business object belongs to a legal entity; TenantContext permits omission only for genuine
organization-level resources.
"""

from uuid import UUID

from ledgerai_contracts.v1.common import ContractModel


class TenantContext(ContractModel):
    tenant_id: UUID
    organization_id: UUID
    legal_entity_id: UUID | None = None


class EntityTenantContext(TenantContext):
    legal_entity_id: UUID
