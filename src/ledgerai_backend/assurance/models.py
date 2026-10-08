"""Tenant-scoped immutable Phase 4 operational records."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ledgerai_backend.database.base import Base
from ledgerai_backend.ingestion.models import TenantScopeMixin, _scope_constraints
from ledgerai_backend.tenancy.models import TimestampVersionMixin


class PostingState(StrEnum):
    REQUESTED = "REQUESTED"
    VALIDATING = "VALIDATING"
    IN_PROGRESS = "IN_PROGRESS"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class PeriodState(StrEnum):
    OPEN = "OPEN"
    CLOSE_REQUESTED = "CLOSE_REQUESTED"
    VALIDATING = "VALIDATING"
    BLOCKED = "BLOCKED"
    READY = "READY"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


class CloseState(StrEnum):
    REQUESTED = "REQUESTED"
    VALIDATING = "VALIDATING"
    BLOCKED = "BLOCKED"
    IN_PROGRESS = "IN_PROGRESS"
    UNKNOWN = "UNKNOWN"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class PostingOperation(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "posting_operations"
    __table_args__ = (
        *_scope_constraints("posting_operations"),
        UniqueConstraint(
            "tenant_id",
            "journal_proposal_id",
            "proposal_version",
            name="uq_posting_effective_proposal",
        ),
        UniqueConstraint("operation_id", name="uq_posting_operation_id"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_posting_idempotency_key"),
        CheckConstraint("proposal_version > 0", name="positive_proposal_version"),
        Index(
            "ix_posting_operations_scope_state",
            "tenant_id",
            "legal_entity_id",
            "state",
            "created_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, default=uuid4)
    journal_proposal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    accounting_period_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    state: Mapped[PostingState] = mapped_column(
        Enum(PostingState, name="posting_state"), nullable=False
    )
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by_principal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(100))


class PostingConfirmation(TenantScopeMixin, Base):
    __tablename__ = "posting_confirmations"
    __table_args__ = (
        *_scope_constraints("posting_confirmations"),
        UniqueConstraint(
            "tenant_id", "posting_operation_id", name="uq_posting_confirmation_operation"
        ),
        UniqueConstraint("tenant_id", "posted_journal_id", name="uq_posting_confirmation_journal"),
        CheckConstraint(
            "octet_length(ledger_references::text) <= 262144", name="bounded_ledger_references"
        ),
        Index(
            "ix_posting_confirmations_scope_time", "tenant_id", "legal_entity_id", "confirmed_at"
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    posting_operation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    posted_journal_id: Mapped[str] = mapped_column(String(200), nullable=False)
    role2_version: Mapped[str] = mapped_column(String(100), nullable=False)
    ledger_references: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AccountingPeriod(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "accounting_periods"
    __table_args__ = (
        *_scope_constraints("accounting_periods"),
        UniqueConstraint(
            "tenant_id",
            "legal_entity_id",
            "period_start",
            "period_end",
            name="uq_accounting_period_boundary",
        ),
        CheckConstraint("period_start <= period_end", name="valid_period_bounds"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="valid_currency"),
        Index(
            "ix_accounting_period_scope_state",
            "tenant_id",
            "legal_entity_id",
            "state",
            "period_start",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[PeriodState] = mapped_column(
        Enum(PeriodState, name="period_state"), nullable=False, default=PeriodState.OPEN
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CloseRun(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "close_runs"
    __table_args__ = (
        *_scope_constraints("close_runs"),
        UniqueConstraint("operation_id", name="uq_close_operation_id"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_close_idempotency_key"),
        Index(
            "ix_close_runs_scope_period",
            "tenant_id",
            "legal_entity_id",
            "accounting_period_id",
            "created_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    accounting_period_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    operation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, default=uuid4)
    state: Mapped[CloseState] = mapped_column(Enum(CloseState, name="close_state"), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by_principal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    role2_version: Mapped[str | None] = mapped_column(String(100))
    last_error_code: Mapped[str | None] = mapped_column(String(100))


class FinancialStatementSnapshot(TenantScopeMixin, Base):
    __tablename__ = "financial_statement_snapshots"
    __table_args__ = (
        *_scope_constraints("financial_statement_snapshots"),
        UniqueConstraint("tenant_id", "role2_snapshot_id", name="uq_statement_snapshot_external"),
        Index(
            "ix_statement_snapshots_scope",
            "tenant_id",
            "legal_entity_id",
            "accounting_period_id",
            "statement_type",
            "as_of",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    accounting_period_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    role2_snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    statement_type: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    role2_version: Mapped[str] = mapped_column(String(100), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FinancialStatementLine(TenantScopeMixin, Base):
    __tablename__ = "financial_statement_lines"
    __table_args__ = (
        *_scope_constraints("financial_statement_lines"),
        UniqueConstraint("tenant_id", "snapshot_id", "line_key", name="uq_statement_line"),
        CheckConstraint("amount IS NOT NULL", name="statement_amount_required"),
        Index("ix_statement_lines_snapshot", "tenant_id", "snapshot_id", "line_key"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    line_key: Mapped[str] = mapped_column(String(200), nullable=False)
    account_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    ledger_references: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)


class AuditEvent(TenantScopeMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        *_scope_constraints("audit_events"),
        UniqueConstraint("audit_event_id", name="uq_audit_event_id"),
        UniqueConstraint("tenant_id", "event_hash", name="uq_audit_event_hash"),
        CheckConstraint("octet_length(metadata::text) <= 65536", name="bounded_audit_metadata"),
        CheckConstraint("event_hash ~ '^[a-f0-9]{64}$'", name="valid_event_hash"),
        CheckConstraint(
            "previous_hash IS NULL OR previous_hash ~ '^[a-f0-9]{64}$'", name="valid_previous_hash"
        ),
        Index(
            "ix_audit_scope_resource", "tenant_id", "resource_type", "resource_id", "occurred_at"
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    audit_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, default=uuid4
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    resource_version: Mapped[str | None] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    audit_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProvenanceEdge(TenantScopeMixin, Base):
    __tablename__ = "provenance_edges"
    __table_args__ = (
        *_scope_constraints("provenance_edges"),
        UniqueConstraint(
            "tenant_id",
            "from_type",
            "from_id",
            "from_version",
            "to_type",
            "to_id",
            "to_version",
            "relation",
            name="uq_provenance_edge",
        ),
        Index("ix_provenance_from", "tenant_id", "from_type", "from_id"),
        Index("ix_provenance_to", "tenant_id", "to_type", "to_id"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    from_type: Mapped[str] = mapped_column(String(100), nullable=False)
    from_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    from_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    to_type: Mapped[str] = mapped_column(String(100), nullable=False)
    to_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    to_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    relation: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProgressEvent(TenantScopeMixin, Base):
    __tablename__ = "progress_events"
    __table_args__ = (
        *_scope_constraints("progress_events"),
        UniqueConstraint("progress_event_id", name="uq_progress_event_id"),
        CheckConstraint("percent IS NULL OR percent BETWEEN 0 AND 100", name="valid_percent"),
        Index("ix_progress_scope_replay", "tenant_id", "legal_entity_id", "occurred_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    progress_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, default=uuid4
    )
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    resource_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    percent: Mapped[int | None] = mapped_column(Integer)
    reason_code: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProgressProjection(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "progress_projections"
    __table_args__ = (
        *_scope_constraints("progress_projections"),
        UniqueConstraint(
            "tenant_id", "resource_type", "resource_id", name="uq_progress_projection_resource"
        ),
        CheckConstraint("percent IS NULL OR percent BETWEEN 0 AND 100", name="valid_percent"),
        Index(
            "ix_progress_projection_scope",
            "tenant_id",
            "legal_entity_id",
            "updated_at",
            "id",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    resource_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    last_event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    percent: Mapped[int | None] = mapped_column(Integer)
    reason_code: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
