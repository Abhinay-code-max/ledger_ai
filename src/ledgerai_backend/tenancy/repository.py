"""Tenant-explicit queries; RLS remains an independent database boundary."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ledgerai_backend.tenancy.models import LegalEntity, Organization, ResourceStatus


class TenancyRepository:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        organization_id: UUID | None,
        legal_entity_id: UUID | None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._organization_id = organization_id
        self._legal_entity_id = legal_entity_id

    async def list_organizations(self, *, limit: int, offset: int) -> list[Organization]:
        query = select(Organization).where(
            Organization.tenant_id == self._tenant_id,
            Organization.status == ResourceStatus.ACTIVE,
        )
        if self._organization_id:
            query = query.where(Organization.id == self._organization_id)
        result = await self._session.scalars(
            query.order_by(Organization.code, Organization.id).limit(limit).offset(offset)
        )
        return list(result)

    async def get_organization(self, organization_id: UUID) -> Organization | None:
        query = select(Organization).where(
            Organization.tenant_id == self._tenant_id,
            Organization.id == organization_id,
            Organization.status == ResourceStatus.ACTIVE,
        )
        if self._organization_id and organization_id != self._organization_id:
            return None
        return await self._session.scalar(query)

    async def list_legal_entities(self, *, limit: int, offset: int) -> list[LegalEntity]:
        query = select(LegalEntity).where(
            LegalEntity.tenant_id == self._tenant_id,
            LegalEntity.status == ResourceStatus.ACTIVE,
        )
        if self._organization_id:
            query = query.where(LegalEntity.organization_id == self._organization_id)
        if self._legal_entity_id:
            query = query.where(LegalEntity.id == self._legal_entity_id)
        result = await self._session.scalars(
            query.order_by(LegalEntity.code, LegalEntity.id).limit(limit).offset(offset)
        )
        return list(result)

    async def get_legal_entity(self, legal_entity_id: UUID) -> LegalEntity | None:
        if self._legal_entity_id and legal_entity_id != self._legal_entity_id:
            return None
        query = select(LegalEntity).where(
            LegalEntity.tenant_id == self._tenant_id,
            LegalEntity.id == legal_entity_id,
            LegalEntity.status == ResourceStatus.ACTIVE,
        )
        if self._organization_id:
            query = query.where(LegalEntity.organization_id == self._organization_id)
        return await self._session.scalar(query)
