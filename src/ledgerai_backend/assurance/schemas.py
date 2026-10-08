"""Strict Phase 4 accounting-assurance API schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ledgerai_backend.assurance.models import CloseState, PeriodState, PostingState


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AccountingPeriodCreate(ApiModel):
    period_start: date
    period_end: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def valid_bounds(self) -> AccountingPeriodCreate:
        if self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        return self


class AccountingPeriodResponse(ApiModel):
    id: UUID
    period_start: date
    period_end: date
    currency: str
    state: PeriodState
    closed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class PostingOperationCreate(ApiModel):
    journal_proposal_id: UUID
    proposal_version: int = Field(ge=1)
    accounting_period_id: UUID


class PostingConfirmationResponse(ApiModel):
    posted_journal_id: str
    role2_version: str
    ledger_references: list[dict[str, Any]]
    confirmed_at: datetime


class PostingOperationResponse(ApiModel):
    id: UUID
    operation_id: UUID
    journal_proposal_id: UUID
    proposal_version: int
    accounting_period_id: UUID
    state: PostingState
    last_error_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    confirmation: PostingConfirmationResponse | None = None


class CloseRunResponse(ApiModel):
    id: UUID
    operation_id: UUID
    accounting_period_id: UUID
    state: CloseState
    role2_version: str | None
    last_error_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class AuditEventResponse(ApiModel):
    audit_event_id: UUID
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: UUID
    resource_version: str | None
    outcome: str
    correlation_id: UUID
    causation_id: UUID | None
    metadata: dict[str, Any] = Field(validation_alias="audit_metadata")
    previous_hash: str | None
    event_hash: str
    occurred_at: datetime


class ProvenanceNode(ApiModel):
    resource_type: str
    resource_id: UUID
    resource_version: str | None = None


class ProvenanceEdgeResponse(ApiModel):
    source: ProvenanceNode
    target: ProvenanceNode
    relation: str


class ProvenanceTraceResponse(ApiModel):
    root: ProvenanceNode
    nodes: list[ProvenanceNode]
    edges: list[ProvenanceEdgeResponse]
    truncated: bool = False


class ProgressEventResponse(ApiModel):
    progress_event_id: UUID
    resource_type: str
    resource_id: UUID
    resource_version: str
    stage: str
    status: str
    correlation_id: UUID
    percent: int | None
    reason_code: str | None
    occurred_at: datetime


class ProgressProjectionResponse(ApiModel):
    resource_type: str
    resource_id: UUID
    resource_version: str
    stage: str
    status: str
    last_event_id: UUID
    correlation_id: UUID
    percent: int | None
    reason_code: str | None
    occurred_at: datetime
    version: int


class StatementLineResponse(ApiModel):
    line_id: str
    account_reference: str
    label: str
    amount: Decimal
    currency: str
    ledger_references: list[dict[str, Any]]


class StatementSnapshotResponse(ApiModel):
    id: UUID
    role2_snapshot_id: UUID
    accounting_period_id: UUID
    statement_type: Literal["TRIAL_BALANCE", "PROFIT_AND_LOSS", "BALANCE_SHEET"]
    currency: str
    as_of: datetime
    role2_version: str
    created_at: datetime
    lines: list[StatementLineResponse]
