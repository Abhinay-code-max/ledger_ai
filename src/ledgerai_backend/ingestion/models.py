"""Phase 2 ingestion, workflow, idempotency, outbox, and inbox persistence."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKeyConstraint,
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
from ledgerai_backend.tenancy.models import TimestampVersionMixin


class DocumentStatus(StrEnum):
    INITIATED = "INITIATED"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    QUARANTINED = "QUARANTINED"
    SCANNING = "SCANNING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ScanStatus(StrEnum):
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    SUSPICIOUS = "SUSPICIOUS"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


class ImportStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTERED = "DEAD_LETTERED"


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTERED = "DEAD_LETTERED"


class IdempotencyStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    TRANSIENT_FAILURE = "TRANSIENT_FAILURE"


def _scope_constraints(prefix: str) -> tuple[ForeignKeyConstraint, ForeignKeyConstraint]:
    return (
        ForeignKeyConstraint(
            ["tenant_id", "organization_id"],
            ["organizations.tenant_id", "organizations.id"],
            name=f"fk_{prefix}_organization_scope",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "organization_id", "legal_entity_id"],
            ["legal_entities.tenant_id", "legal_entities.organization_id", "legal_entities.id"],
            name=f"fk_{prefix}_legal_entity_scope",
        ),
    )


class TenantScopeMixin:
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    legal_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class Document(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        *_scope_constraints("documents"),
        UniqueConstraint("tenant_id", "id", name="uq_documents_tenant_id_id"),
        Index("ix_documents_scope_created", "tenant_id", "legal_entity_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"), default=DocumentStatus.INITIATED
    )
    created_by_principal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class DocumentVersion(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        *_scope_constraints("document_versions"),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["documents.tenant_id", "documents.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_document_versions_tenant_id_id"),
        UniqueConstraint("tenant_id", "document_id", "version_number"),
        UniqueConstraint("object_key"),
        CheckConstraint("expected_byte_size > 0", name="positive_expected_size"),
        CheckConstraint(
            "actual_byte_size IS NULL OR actual_byte_size > 0", name="positive_actual_size"
        ),
        CheckConstraint("expected_sha256 ~ '^[a-f0-9]{64}$'", name="expected_hash"),
        CheckConstraint(
            "actual_sha256 IS NULL OR actual_sha256 ~ '^[a-f0-9]{64}$'", name="actual_hash"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(300), nullable=False)
    storage_version: Mapped[str | None] = mapped_column(String(255))
    expected_media_type: Mapped[str] = mapped_column(String(80), nullable=False)
    detected_media_type: Mapped[str | None] = mapped_column(String(80))
    expected_byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actual_byte_size: Mapped[int | None] = mapped_column(BigInteger)
    expected_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    actual_sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", create_type=False),
        default=DocumentStatus.UPLOADING,
    )
    failure_code: Mapped[str | None] = mapped_column(String(80))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentScanResult(TenantScopeMixin, Base):
    __tablename__ = "document_scan_results"
    __table_args__ = (
        *_scope_constraints("document_scan_results"),
        ForeignKeyConstraint(
            ["tenant_id", "document_version_id"],
            ["document_versions.tenant_id", "document_versions.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("content_sha256 ~ '^[a-f0-9]{64}$'", name="content_hash"),
        Index(
            "ix_document_scan_results_version_time",
            "tenant_id",
            "document_version_id",
            "scanned_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_version_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus, name="scan_status"))
    scanner_name: Mapped[str] = mapped_column(String(80), nullable=False)
    scanner_version: Mapped[str] = mapped_column(String(80), nullable=False)
    signature_version: Mapped[str | None] = mapped_column(String(80))
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TransactionImport(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "transaction_imports"
    __table_args__ = (
        *_scope_constraints("transaction_imports"),
        UniqueConstraint("tenant_id", "id", name="uq_transaction_imports_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "legal_entity_id",
            "bank_account_id",
            "source_sha256",
            name="uq_transaction_imports_source_scope",
        ),
        CheckConstraint("source_sha256 ~ '^[a-f0-9]{64}$'", name="source_hash"),
        CheckConstraint("accepted_count >= 0 AND rejected_count >= 0", name="nonnegative_counts"),
        Index(
            "ix_transaction_imports_scope_created",
            "tenant_id",
            "legal_entity_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    bank_account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus, name="import_status"))
    accepted_count: Mapped[int] = mapped_column(default=0, server_default="0")
    rejected_count: Mapped[int] = mapped_column(default=0, server_default="0")
    created_by_principal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class BankTransaction(TenantScopeMixin, Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        *_scope_constraints("bank_transactions"),
        ForeignKeyConstraint(
            ["tenant_id", "import_id"],
            ["transaction_imports.tenant_id", "transaction_imports.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_bank_transactions_tenant_id_id"),
        UniqueConstraint("tenant_id", "bank_account_id", "source_fingerprint"),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="iso_currency"),
        Index(
            "ix_bank_transactions_scope_date", "tenant_id", "legal_entity_id", "booking_date", "id"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    bank_account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    direction: Mapped[str] = mapped_column(String(6), nullable=False)
    narration: Mapped[str] = mapped_column(String(1024), default="", server_default="")
    reference: Mapped[str | None] = mapped_column(String(255))
    counterparty_name: Mapped[str | None] = mapped_column(String(255))
    counterparty_account: Mapped[str | None] = mapped_column(String(100))
    external_source_id: Mapped[str | None] = mapped_column(String(255))
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransactionImportError(TenantScopeMixin, Base):
    __tablename__ = "transaction_import_errors"
    __table_args__ = (
        *_scope_constraints("transaction_import_errors"),
        ForeignKeyConstraint(
            ["tenant_id", "import_id"],
            ["transaction_imports.tenant_id", "transaction_imports.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "import_id", "source_row_number"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str] = mapped_column(String(80), nullable=False)
    safe_message: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessingJob(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        *_scope_constraints("processing_jobs"),
        UniqueConstraint("tenant_id", "id", name="uq_processing_jobs_tenant_id_id"),
        CheckConstraint(
            "attempt_number >= 0 AND maximum_attempts >= 1 AND attempt_number <= maximum_attempts",
            name="attempt_bounds",
        ),
        Index("ix_processing_jobs_status_schedule", "tenant_id", "status", "scheduled_for", "id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    handler_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status"))
    attempt_number: Mapped[int] = mapped_column(default=0, server_default="0")
    maximum_attempts: Mapped[int] = mapped_column(default=5, server_default="5")
    input_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    output_reference: Mapped[str | None] = mapped_column(String(300))
    queue_name: Mapped[str] = mapped_column(String(100), nullable=False)
    retryable: Mapped[bool | None]
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(300))
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobAttempt(TenantScopeMixin, Base):
    __tablename__ = "job_attempts"
    __table_args__ = (
        *_scope_constraints("job_attempts"),
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["processing_jobs.tenant_id", "processing_jobs.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "job_id", "attempt_number"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DeliveryStatus] = mapped_column(Enum(DeliveryStatus, name="attempt_status"))
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(300))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxEvent(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        *_scope_constraints("outbox_events"),
        UniqueConstraint("event_id"),
        CheckConstraint("attempt_count >= 0", name="attempt_count"),
        Index("ix_outbox_pending", "status", "next_attempt_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    producer: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_reference: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[DeliveryStatus] = mapped_column(Enum(DeliveryStatus, name="outbox_status"))
    attempt_count: Mapped[int] = mapped_column(default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))


class ConsumerInbox(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "consumer_inbox"
    __table_args__ = (
        *_scope_constraints("consumer_inbox"),
        UniqueConstraint("consumer_name", "event_id"),
        CheckConstraint("attempt_count >= 0", name="attempt_count"),
        Index("ix_consumer_inbox_status", "tenant_id", "status", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    consumer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    consumer_version: Mapped[str] = mapped_column(String(40), nullable=False)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[DeliveryStatus] = mapped_column(Enum(DeliveryStatus, name="inbox_status"))
    attempt_count: Mapped[int] = mapped_column(default=0, server_default="0")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))


class IdempotencyRecord(TenantScopeMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        *_scope_constraints("idempotency_records"),
        UniqueConstraint("tenant_id", "actor_id", "operation", "idempotency_key"),
        CheckConstraint("request_fingerprint ~ '^[a-f0-9]{64}$'", name="request_hash"),
        Index("ix_idempotency_expiry", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[IdempotencyStatus] = mapped_column(
        Enum(IdempotencyStatus, name="idempotency_status")
    )
    response_resource_type: Mapped[str | None] = mapped_column(String(80))
    response_resource_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
