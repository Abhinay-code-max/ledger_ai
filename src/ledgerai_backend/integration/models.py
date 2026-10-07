"""Tenant-scoped Phase 3 evidence, policy, and approval persistence."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ledgerai_backend.database.base import Base
from ledgerai_backend.ingestion.models import TenantScopeMixin, _scope_constraints
from ledgerai_backend.tenancy.models import TimestampVersionMixin


class ExtractionStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ValidationOutcome(StrEnum):
    VALIDATED = "VALIDATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"


class ProposalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ExceptionSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExceptionResolution(StrEnum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class PolicyOutcome(StrEnum):
    AUTO_ELIGIBLE = "AUTO_ELIGIBLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ESCALATED = "ESCALATED"
    BLOCKED = "BLOCKED"


class ApprovalStatus(StrEnum):
    OPEN = "OPEN"
    APPROVED = "APPROVED"
    CORRECTED = "CORRECTED"
    REJECTED = "REJECTED"
    EVIDENCE_REQUESTED = "EVIDENCE_REQUESTED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class ApprovalActionType(StrEnum):
    APPROVE = "APPROVE"
    CORRECT = "CORRECT"
    REJECT = "REJECT"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    ESCALATE = "ESCALATE"


class ServiceCallStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"
    UNKNOWN = "UNKNOWN"


class DocumentExtraction(TenantScopeMixin, Base):
    __tablename__ = "document_extractions"
    __table_args__ = (
        *_scope_constraints("document_extractions"),
        ForeignKeyConstraint(
            ["tenant_id", "document_version_id"],
            ["document_versions.tenant_id", "document_versions.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_document_extractions_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "document_version_id",
            "producer_result_id",
            name="uq_document_extractions_producer_result",
        ),
        CheckConstraint("extraction_version > 0", name="positive_extraction_version"),
        CheckConstraint("octet_length(contract_payload::text) <= 1048576", name="bounded_payload"),
        Index(
            "ix_document_extractions_scope_status",
            "tenant_id",
            "legal_entity_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    extraction_version: Mapped[int] = mapped_column(Integer, nullable=False)
    producer_result_id: Mapped[str] = mapped_column(String(200), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    producer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    producer_version: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120))
    model_version: Mapped[str | None] = mapped_column(String(80))
    prompt_template_version: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, name="extraction_status"), nullable=False
    )
    review_disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_outcome: Mapped[ValidationOutcome] = mapped_column(
        Enum(ValidationOutcome, name="validation_outcome"), nullable=False
    )
    contract_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExtractionField(TenantScopeMixin, Base):
    __tablename__ = "extraction_fields"
    __table_args__ = (
        *_scope_constraints("extraction_fields"),
        ForeignKeyConstraint(
            ["tenant_id", "extraction_id"],
            ["document_extractions.tenant_id", "document_extractions.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence_range"
        ),
        CheckConstraint("octet_length(value_json::text) <= 65536", name="bounded_value"),
        CheckConstraint("octet_length(provenance::text) <= 262144", name="bounded_provenance"),
        Index("ix_extraction_fields_extraction", "tenant_id", "extraction_id", "field_name"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    extraction_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    line_number: Mapped[int | None] = mapped_column(Integer)
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    value_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    provenance: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)


class MatchProposal(TenantScopeMixin, Base):
    __tablename__ = "match_proposals"
    __table_args__ = (
        *_scope_constraints("match_proposals"),
        UniqueConstraint("tenant_id", "id", name="uq_match_proposals_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "external_proposal_id",
            "proposal_version",
            name="uq_match_proposal_external_version",
        ),
        CheckConstraint("proposal_version > 0", name="positive_proposal_version"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint("octet_length(contract_payload::text) <= 1048576", name="bounded_payload"),
        Index(
            "ix_match_proposals_scope_status",
            "tenant_id",
            "legal_entity_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    external_proposal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    match_type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(ProposalStatus, name="match_proposal_status"), nullable=False
    )
    producer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    producer_version: Mapped[str] = mapped_column(String(80), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(80), nullable=False)
    contract_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MatchProposalItem(TenantScopeMixin, Base):
    __tablename__ = "match_proposal_items"
    __table_args__ = (
        *_scope_constraints("match_proposal_items"),
        ForeignKeyConstraint(
            ["tenant_id", "match_proposal_id"],
            ["match_proposals.tenant_id", "match_proposals.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "match_proposal_id",
            "resource_type",
            "resource_id",
            name="uq_match_proposal_item",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    match_proposal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    resource_version: Mapped[str | None] = mapped_column(String(128))


class WorkflowException(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "exceptions"
    __table_args__ = (
        *_scope_constraints("exceptions"),
        UniqueConstraint("tenant_id", "id", name="uq_exceptions_tenant_id_id"),
        UniqueConstraint("tenant_id", "external_exception_id", name="uq_exceptions_external_id"),
        CheckConstraint("octet_length(contract_payload::text) <= 1048576", name="bounded_payload"),
        Index(
            "ix_exceptions_review_queue",
            "tenant_id",
            "legal_entity_id",
            "resolution_status",
            "severity",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    external_exception_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    exception_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[ExceptionSeverity] = mapped_column(
        Enum(ExceptionSeverity, name="exception_severity"), nullable=False
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    resolution_status: Mapped[ExceptionResolution] = mapped_column(
        Enum(ExceptionResolution, name="exception_resolution"), nullable=False
    )
    resolution_reference: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    contract_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class JournalProposal(TenantScopeMixin, Base):
    __tablename__ = "journal_proposals"
    __table_args__ = (
        *_scope_constraints("journal_proposals"),
        UniqueConstraint("tenant_id", "id", name="uq_journal_proposals_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "proposal_series_id",
            "proposal_version",
            name="uq_journal_proposal_version",
        ),
        CheckConstraint("proposal_version > 0", name="positive_proposal_version"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format"),
        CheckConstraint("accounting_validation = 'NOT_VALIDATED'", name="not_validated"),
        CheckConstraint("posting_status = 'UNPOSTED'", name="unposted"),
        CheckConstraint("octet_length(contract_payload::text) <= 1048576", name="bounded_payload"),
        Index(
            "ix_journal_proposals_scope_series",
            "tenant_id",
            "legal_entity_id",
            "proposal_series_id",
            "proposal_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    proposal_series_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_journal_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    accounting_validation: Mapped[str] = mapped_column(
        String(20), nullable=False, default="NOT_VALIDATED"
    )
    posting_status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNPOSTED")
    producer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    producer_version: Mapped[str] = mapped_column(String(80), nullable=False)
    contract_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_principal_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JournalProposalLine(TenantScopeMixin, Base):
    __tablename__ = "journal_proposal_lines"
    __table_args__ = (
        *_scope_constraints("journal_proposal_lines"),
        ForeignKeyConstraint(
            ["tenant_id", "journal_proposal_id"],
            ["journal_proposals.tenant_id", "journal_proposals.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id", "journal_proposal_id", "line_id", name="uq_journal_proposal_line"
        ),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format"),
        CheckConstraint("direction IN ('DEBIT', 'CREDIT')", name="direction"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    journal_proposal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    line_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    account_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    source_evidence: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)


class PolicySet(TenantScopeMixin, Base):
    __tablename__ = "policy_sets"
    __table_args__ = (
        *_scope_constraints("policy_sets"),
        UniqueConstraint("tenant_id", "id", name="uq_policy_sets_tenant_id_id"),
        UniqueConstraint(
            "tenant_id", "legal_entity_id", "code", "policy_version", name="uq_policy_set_version"
        ),
        Index(
            "uq_policy_sets_active_scope",
            "tenant_id",
            "legal_entity_id",
            "code",
            unique=True,
            postgresql_where="active_from IS NOT NULL AND retired_at IS NULL",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    default_outcome: Mapped[PolicyOutcome] = mapped_column(
        Enum(PolicyOutcome, name="policy_outcome"),
        nullable=False,
        default=PolicyOutcome.REVIEW_REQUIRED,
    )
    active_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PolicyRule(TenantScopeMixin, Base):
    __tablename__ = "policy_rules"
    __table_args__ = (
        *_scope_constraints("policy_rules"),
        ForeignKeyConstraint(
            ["tenant_id", "policy_set_id"],
            ["policy_sets.tenant_id", "policy_sets.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "policy_set_id", "rule_id", name="uq_policy_rule_id"),
        CheckConstraint("priority >= 0", name="nonnegative_priority"),
        CheckConstraint("octet_length(conditions::text) <= 65536", name="bounded_conditions"),
        Index("ix_policy_rules_order", "tenant_id", "policy_set_id", "priority", "rule_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    policy_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    conditions: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    outcome: Mapped[PolicyOutcome] = mapped_column(
        Enum(PolicyOutcome, name="policy_outcome", create_type=False), nullable=False
    )
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    explanation: Mapped[str] = mapped_column(String(500), nullable=False)


class PolicyDecision(TenantScopeMixin, Base):
    __tablename__ = "policy_decisions"
    __table_args__ = (
        *_scope_constraints("policy_decisions"),
        ForeignKeyConstraint(
            ["tenant_id", "policy_set_id"],
            ["policy_sets.tenant_id", "policy_sets.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_policy_decisions_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "subject_type",
            "subject_id",
            "subject_version",
            "policy_set_id",
            name="uq_policy_decision_replay",
        ),
        CheckConstraint("octet_length(evaluated_inputs::text) <= 262144", name="bounded_inputs"),
        Index("ix_policy_decisions_scope_time", "tenant_id", "legal_entity_id", "decided_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    subject_version: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    policy_set_version: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[PolicyOutcome] = mapped_column(
        Enum(PolicyOutcome, name="policy_outcome", create_type=False), nullable=False
    )
    evaluated_inputs: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    matched_rule_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str] = mapped_column(String(1000), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApprovalRequest(TenantScopeMixin, TimestampVersionMixin, Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        *_scope_constraints("approval_requests"),
        UniqueConstraint("tenant_id", "id", name="uq_approval_requests_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "subject_type",
            "subject_id",
            "subject_version",
            name="uq_approval_request_subject_version",
        ),
        Index(
            "ix_approval_requests_queue",
            "tenant_id",
            "legal_entity_id",
            "status",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    subject_version: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_decision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status"), nullable=False, default=ApprovalStatus.OPEN
    )
    maker_principal_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    maker_checker_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    terminal_action_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class ApprovalAction(TenantScopeMixin, Base):
    __tablename__ = "approval_actions"
    __table_args__ = (
        *_scope_constraints("approval_actions"),
        ForeignKeyConstraint(
            ["tenant_id", "approval_request_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_approval_actions_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "actor_principal_id",
            "idempotency_key",
            name="uq_approval_action_idempotency",
        ),
        CheckConstraint(
            "octet_length(structured_corrections::text) <= 262144", name="bounded_corrections"
        ),
        Index("ix_approval_actions_request_time", "tenant_id", "approval_request_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    approval_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reviewed_resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    reviewed_resource_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reviewed_resource_version: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[ApprovalActionType] = mapped_column(
        Enum(ApprovalActionType, name="approval_action_type"), nullable=False
    )
    actor_principal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    actor_roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000))
    structured_corrections: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    separation_of_duties_checked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ServiceCallAttempt(TenantScopeMixin, Base):
    __tablename__ = "service_call_attempts"
    __table_args__ = (
        *_scope_constraints("service_call_attempts"),
        UniqueConstraint(
            "tenant_id",
            "service_name",
            "operation_id",
            "attempt_number",
            name="uq_service_call_attempt",
        ),
        Index("ix_service_call_attempts_operation", "tenant_id", "service_name", "operation_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    service_name: Mapped[str] = mapped_column(String(80), nullable=False)
    operation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ServiceCallStatus] = mapped_column(
        Enum(ServiceCallStatus, name="service_call_status"), nullable=False
    )
    response_code: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
