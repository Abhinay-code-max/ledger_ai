"""Role 2 accounting-boundary contracts; Role 4 only orchestrates these results."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ledgerai_contracts.v1.common import (
    ContractModel,
    CorrelationMetadata,
    CurrencyCode,
    Money,
    ProducerMetadata,
    ResourceReference,
    SchemaVersion,
    UtcDateTime,
    ValidationIssue,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class AccountingValidationResult(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    operation_id: UUID
    proposal_id: UUID
    proposal_version: int = Field(ge=1)
    outcome: Literal["ACCEPTED", "VALIDATED", "REJECTED", "UNKNOWN", "FAILED"]
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=100)
    producer: ProducerMetadata
    correlation: CorrelationMetadata

    @model_validator(mode="after")
    def issues_match_outcome(self) -> AccountingValidationResult:
        if self.outcome == "REJECTED" and not self.issues:
            raise ValueError("rejected validation requires at least one issue")
        return self


class JournalPostingRequest(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    operation_id: UUID
    proposal: ResourceReference
    proposal_version: int = Field(ge=1)
    accounting_period_id: UUID
    requested_at: UtcDateTime
    producer: ProducerMetadata
    correlation: CorrelationMetadata


class JournalPostingResult(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    operation_id: UUID
    proposal_id: UUID
    proposal_version: int = Field(ge=1)
    outcome: Literal["POSTED", "REJECTED", "IN_PROGRESS", "UNKNOWN", "FAILED"]
    posted_journal_id: str | None = Field(default=None, max_length=200)
    posted_at: UtcDateTime | None = None
    ledger_references: list[ResourceReference] = Field(default_factory=list, max_length=200)
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=100)
    producer: ProducerMetadata
    correlation: CorrelationMetadata

    @field_validator("posted_journal_id")
    @classmethod
    def nonempty_journal(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def posted_result_is_complete(self) -> JournalPostingResult:
        has_confirmation = self.posted_journal_id is not None and self.posted_at is not None
        if (self.outcome == "POSTED") != has_confirmation:
            raise ValueError("only posted results contain a complete journal confirmation")
        if self.outcome == "POSTED" and not self.ledger_references:
            raise ValueError("posted results require ledger references")
        return self


class PostingStatusResult(JournalPostingResult):
    pass


class PeriodCloseRequest(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    operation_id: UUID
    accounting_period_id: UUID
    period_start: date
    period_end: date
    requested_at: UtcDateTime
    producer: ProducerMetadata
    correlation: CorrelationMetadata

    @model_validator(mode="after")
    def valid_period(self) -> PeriodCloseRequest:
        if self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        return self


class PeriodCloseValidationResult(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    operation_id: UUID
    accounting_period_id: UUID
    outcome: Literal["VALIDATED", "BLOCKED", "REJECTED", "UNKNOWN", "FAILED"]
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=100)
    producer: ProducerMetadata
    correlation: CorrelationMetadata


class PeriodCloseResult(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    operation_id: UUID
    accounting_period_id: UUID
    outcome: Literal["CLOSED", "BLOCKED", "REJECTED", "IN_PROGRESS", "UNKNOWN", "FAILED"]
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=100)
    closed_at: UtcDateTime | None = None
    producer: ProducerMetadata
    correlation: CorrelationMetadata

    @model_validator(mode="after")
    def closed_result_is_complete(self) -> PeriodCloseResult:
        if (self.outcome == "CLOSED") != (self.closed_at is not None):
            raise ValueError("only closed results contain closed_at")
        return self


class FinancialStatementRequest(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    operation_id: UUID
    accounting_period_id: UUID
    statement_type: Literal["TRIAL_BALANCE", "PROFIT_AND_LOSS", "BALANCE_SHEET"]
    as_of: UtcDateTime
    correlation: CorrelationMetadata


class FinancialStatementLine(ContractModel):
    line_id: str = Field(min_length=1, max_length=200)
    account_reference: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=300)
    amount: Money
    ledger_references: list[ResourceReference] = Field(default_factory=list, max_length=200)


class FinancialStatementSnapshot(ContractModel):
    schema_version: SchemaVersion
    snapshot_id: UUID
    tenant_context: EntityTenantContext
    accounting_period_id: UUID
    statement_type: Literal["TRIAL_BALANCE", "PROFIT_AND_LOSS", "BALANCE_SHEET"]
    currency: CurrencyCode
    as_of: UtcDateTime
    status: Literal["AVAILABLE", "IN_PROGRESS", "UNAVAILABLE", "FAILED"]
    lines: list[FinancialStatementLine] = Field(default_factory=list, max_length=10000)
    producer: ProducerMetadata
    correlation: CorrelationMetadata

    @model_validator(mode="after")
    def available_snapshot_has_lines(self) -> FinancialStatementSnapshot:
        if self.status == "AVAILABLE" and not self.lines:
            raise ValueError("available statements require at least one line")
        if self.status != "AVAILABLE" and self.lines:
            raise ValueError("unavailable statements cannot contain lines")
        return self


class ProvenanceEdge(ContractModel):
    source: ResourceReference
    target: ResourceReference
    relation: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z][A-Z0-9_]*$")


class ProvenanceTrace(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    root: ResourceReference
    nodes: list[ResourceReference] = Field(max_length=500)
    edges: list[ProvenanceEdge] = Field(max_length=1000)
    missing_references: list[ResourceReference] = Field(default_factory=list, max_length=100)


class ProgressEvent(ContractModel):
    schema_version: SchemaVersion
    event_id: UUID
    tenant_context: EntityTenantContext
    resource: ResourceReference
    stage: str = Field(min_length=1, max_length=80)
    status: str = Field(min_length=1, max_length=80)
    occurred_at: UtcDateTime
    correlation_id: UUID
    percent: int | None = Field(default=None, ge=0, le=100)
    reason_code: str | None = Field(default=None, max_length=100)


class ProgressProjection(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    resource: ResourceReference
    stage: str = Field(min_length=1, max_length=80)
    status: str = Field(min_length=1, max_length=80)
    last_event_id: UUID
    occurred_at: UtcDateTime
    correlation_id: UUID
    percent: int | None = Field(default=None, ge=0, le=100)
    reason_code: str | None = Field(default=None, max_length=100)
