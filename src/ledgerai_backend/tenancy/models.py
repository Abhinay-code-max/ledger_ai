"""Typed Phase 1 tenancy and authorization persistence models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ledgerai_backend.database.base import Base


class ResourceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class MembershipStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class TimestampVersionMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)


class Tenant(TimestampVersionMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("name = btrim(name) AND length(name) > 0", name="name_nonempty"),
        CheckConstraint(
            "code = lower(code) AND code ~ '^[a-z0-9][a-z0-9-]*$'", name="code_normalized"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[ResourceStatus] = mapped_column(
        Enum(ResourceStatus, name="resource_status"), default=ResourceStatus.ACTIVE, nullable=False
    )


class Organization(TimestampVersionMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_organizations_tenant_id_id"),
        UniqueConstraint("tenant_id", "code", name="uq_organizations_tenant_code"),
        CheckConstraint("name = btrim(name) AND length(name) > 0", name="name_nonempty"),
        CheckConstraint(
            "code = lower(code) AND code ~ '^[a-z0-9][a-z0-9-]*$'", name="code_normalized"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[ResourceStatus] = mapped_column(
        Enum(ResourceStatus, name="resource_status", create_type=False),
        default=ResourceStatus.ACTIVE,
        nullable=False,
    )


class LegalEntity(TimestampVersionMixin, Base):
    __tablename__ = "legal_entities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "organization_id"],
            ["organizations.tenant_id", "organizations.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "organization_id", "id", name="uq_legal_entities_scope_id"),
        UniqueConstraint(
            "tenant_id", "organization_id", "code", name="uq_legal_entities_scope_code"
        ),
        CheckConstraint(
            "legal_name = btrim(legal_name) AND length(legal_name) > 0", name="legal_name_nonempty"
        ),
        CheckConstraint(
            "display_name = btrim(display_name) AND length(display_name) > 0",
            name="display_name_nonempty",
        ),
        CheckConstraint(
            "code = lower(code) AND code ~ '^[a-z0-9][a-z0-9-]*$'", name="code_normalized"
        ),
        CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="country_code_format"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(250), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    status: Mapped[ResourceStatus] = mapped_column(
        Enum(ResourceStatus, name="resource_status", create_type=False),
        default=ResourceStatus.ACTIVE,
        nullable=False,
    )


class Principal(TimestampVersionMixin, Base):
    __tablename__ = "principals"
    __table_args__ = (
        UniqueConstraint("issuer", "external_subject"),
        CheckConstraint("issuer = btrim(issuer) AND length(issuer) > 0", name="issuer_nonempty"),
        CheckConstraint(
            "external_subject = btrim(external_subject) AND length(external_subject) > 0",
            name="subject_nonempty",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    issuer: Mapped[str] = mapped_column(String(500), nullable=False)
    external_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[ResourceStatus] = mapped_column(
        Enum(ResourceStatus, name="resource_status", create_type=False),
        default=ResourceStatus.ACTIVE,
        nullable=False,
    )


class Membership(TimestampVersionMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "organization_id"],
            ["organizations.tenant_id", "organizations.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "organization_id", "legal_entity_id"],
            ["legal_entities.tenant_id", "legal_entities.organization_id", "legal_entities.id"],
        ),
        UniqueConstraint("tenant_id", "id", name="uq_memberships_tenant_id_id"),
        CheckConstraint(
            "legal_entity_id IS NULL OR organization_id IS NOT NULL", name="scope_hierarchy"
        ),
        CheckConstraint("revoked_at IS NULL OR status = 'REVOKED'", name="revocation_state"),
        Index(
            "uq_memberships_active_scope",
            "tenant_id",
            "principal_id",
            "organization_id",
            "legal_entity_id",
            unique=True,
            postgresql_where="status = 'ACTIVE'",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    principal_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("principals.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    legal_entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, name="membership_status"),
        default=MembershipStatus.ACTIVE,
        nullable=False,
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_principal_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_principal_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))


class Role(TimestampVersionMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_roles_tenant_id_id"),
        UniqueConstraint("tenant_id", "code", name="uq_roles_tenant_code"),
        CheckConstraint(
            "code = lower(code) AND code ~ '^[a-z][a-z0-9-]*$'", name="code_normalized"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (
        CheckConstraint(
            "code = lower(code) AND code ~ '^[a-z][-a-z0-9._:]*$'", name="code_normalized"
        ),
    )

    code: Mapped[str] = mapped_column(String(120), primary_key=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "role_id"], ["roles.tenant_id", "roles.id"], ondelete="CASCADE"
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    role_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    permission_code: Mapped[str] = mapped_column(
        String(120), ForeignKey("permissions.code", ondelete="CASCADE"), primary_key=True
    )


class RoleAssignment(TimestampVersionMixin, Base):
    __tablename__ = "role_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["memberships.tenant_id", "memberships.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "role_id"], ["roles.tenant_id", "roles.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "organization_id"], ["organizations.tenant_id", "organizations.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "organization_id", "legal_entity_id"],
            ["legal_entities.tenant_id", "legal_entities.organization_id", "legal_entities.id"],
        ),
        CheckConstraint(
            "legal_entity_id IS NULL OR organization_id IS NOT NULL", name="scope_hierarchy"
        ),
        Index(
            "uq_role_assignments_scope",
            "tenant_id",
            "membership_id",
            "role_id",
            "organization_id",
            "legal_entity_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    role_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    organization_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    legal_entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    assigned_by_principal_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
