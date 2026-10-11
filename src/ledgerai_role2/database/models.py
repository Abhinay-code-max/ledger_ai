"""SQLAlchemy persistence models for Role 2 Accounting Core."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ledgerai_backend.database.base import Base
from ledgerai_role2.domain.models import (
    AccountType,
    Direction,
    NormalBalance,
    PeriodStatus,
    StatementStatus,
    StatementType,
)
from ledgerai_role2.domain.state_machine import PostingState


class Role2TenantScopeMixin:
    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    legal_entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)


class Role2Account(Role2TenantScopeMixin, Base):
    __tablename__ = "role2_accounts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "legal_entity_id",
            "account_code",
            name="uq_role2_accounts_scope_code",
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_role2_accounts_currency"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    account_code: Mapped[str] = mapped_column(String(160), nullable=False)
    account_name: Mapped[str] = mapped_column(String(300), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        Enum(
            AccountType, name="role2_account_type", values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
    )
    normal_balance: Mapped[NormalBalance] = mapped_column(
        Enum(
            NormalBalance,
            name="role2_normal_balance",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Role2AccountingPeriod(Role2TenantScopeMixin, Base):
    __tablename__ = "role2_accounting_periods"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "legal_entity_id",
            "period_start",
            "period_end",
            name="uq_role2_periods_boundary",
        ),
        CheckConstraint("period_start <= period_end", name="ck_role2_periods_valid_range"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[PeriodStatus] = mapped_column(
        Enum(
            PeriodStatus, name="role2_period_status", values_callable=lambda x: [e.value for e in x]
        ),
        default=PeriodStatus.OPEN,
        nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Role2PostedJournal(Role2TenantScopeMixin, Base):
    __tablename__ = "role2_posted_journals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operation_id", name="uq_role2_posted_journal_operation"),
        UniqueConstraint("tenant_id", "id", name="uq_role2_posted_journal_id"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_role2_posted_journals_currency"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    proposal_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    accounting_period_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    journal_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    reversal_of_journal_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    is_reversed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class Role2JournalLine(Role2TenantScopeMixin, Base):
    __tablename__ = "role2_journal_lines"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_role2_journal_lines_amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_role2_journal_lines_currency"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    journal_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    account_reference: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    direction: Mapped[Direction] = mapped_column(
        Enum(Direction, name="role2_direction", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )


class Role2PostingOperation(Role2TenantScopeMixin, Base):
    __tablename__ = "role2_posting_operations"
    __table_args__ = (UniqueConstraint("tenant_id", "operation_id", name="uq_role2_posting_op_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    proposal_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    accounting_period_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[PostingState] = mapped_column(
        Enum(
            PostingState, name="role2_posting_state", values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
    )
    posted_journal_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Role2PeriodCloseOperation(Role2TenantScopeMixin, Base):
    __tablename__ = "role2_period_close_operations"
    __table_args__ = (UniqueConstraint("tenant_id", "operation_id", name="uq_role2_close_op_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    accounting_period_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Role2StatementSnapshot(Role2TenantScopeMixin, Base):
    __tablename__ = "role2_statement_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "snapshot_id", name="uq_role2_snapshot_id"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_role2_statement_snapshots_currency"),
    )

    snapshot_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    accounting_period_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    statement_type: Mapped[StatementType] = mapped_column(
        Enum(
            StatementType,
            name="role2_statement_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[StatementStatus] = mapped_column(
        Enum(
            StatementStatus,
            name="role2_statement_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Role2StatementLine(Role2TenantScopeMixin, Base):
    __tablename__ = "role2_statement_lines"
    __table_args__ = (
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_role2_statement_lines_currency"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    line_id: Mapped[str] = mapped_column(String(200), nullable=False)
    account_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    ledger_references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )


class Role2ProposalRecord(Role2TenantScopeMixin, Base):
    __tablename__ = "role2_proposal_registry"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "proposal_id", "proposal_version", name="uq_role2_proposal_ver"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_journal_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    lines_payload: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    source_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    approval_decision: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
