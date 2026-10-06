"""Transaction-local tenant RLS context and narrow membership bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class BootstrapAuthorization:
    principal_id: UUID
    membership_id: UUID
    tenant_id: UUID
    organization_id: UUID | None
    legal_entity_id: UUID | None
    roles: frozenset[str]
    permissions: frozenset[str]


async def resolve_bootstrap_authorization(
    session: AsyncSession,
    *,
    issuer: str,
    subject: str,
    workspace_code: str,
    organization_id: UUID | None,
    legal_entity_id: UUID | None,
) -> BootstrapAuthorization | None:
    result = await session.execute(
        text(
            """
            SELECT * FROM ledgerai.bootstrap_authorization(
                :issuer, :subject, :workspace_code, :organization_id, :legal_entity_id
            )
            """
        ),
        {
            "issuer": issuer,
            "subject": subject,
            "workspace_code": workspace_code,
            "organization_id": organization_id,
            "legal_entity_id": legal_entity_id,
        },
    )
    row = result.mappings().one_or_none()
    if row is None:
        return None
    return BootstrapAuthorization(
        principal_id=row["principal_id"],
        membership_id=row["membership_id"],
        tenant_id=row["tenant_id"],
        organization_id=row["organization_id"],
        legal_entity_id=row["legal_entity_id"],
        roles=frozenset(row["roles"] or []),
        permissions=frozenset(row["permissions"] or []),
    )


async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def assert_database_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    result = await session.execute(
        text("SELECT nullif(current_setting('app.tenant_id', true), '')::uuid")
    )
    if result.scalar_one() != tenant_id:
        raise RuntimeError("database tenant context was not applied")
