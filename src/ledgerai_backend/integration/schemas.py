"""Strict request and response schemas for Phase 3 review APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ledgerai_backend.integration.models import ApprovalActionType, ApprovalStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class EvidenceResourceResponse(ApiModel):
    id: UUID
    contract_payload: dict[str, Any]
    created_at: datetime


class ExceptionResponse(EvidenceResourceResponse):
    exception_type: str
    severity: str
    resolution_status: str


class MatchProposalResponse(EvidenceResourceResponse):
    proposal_version: int
    match_type: str
    status: str


class JournalProposalResponse(EvidenceResourceResponse):
    proposal_series_id: UUID
    proposal_version: int
    accounting_validation: str
    posting_status: str


class ApprovalRequestResponse(ApiModel):
    id: UUID
    subject_type: str
    subject_id: UUID
    subject_version: str
    status: ApprovalStatus
    maker_checker_required: bool
    expires_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime


class Page(ApiModel):
    items: list[Any]
    next_cursor: UUID | None = None


class ApprovalActionRequest(ApiModel):
    reviewed_resource_version: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$"
    )
    reason: str | None = Field(default=None, min_length=1, max_length=1000)
    structured_corrections: dict[str, Any] | None = None

    @model_validator(mode="after")
    def bound_corrections(self) -> ApprovalActionRequest:
        if self.structured_corrections is not None:
            if len(self.structured_corrections) > 20:
                raise ValueError("too many correction fields")
            allowed = {"proposed_journal_date", "explanation", "lines"}
            if set(self.structured_corrections).difference(allowed):
                raise ValueError("corrections contain unsupported fields")
        return self


class ApprovalActionResponse(ApiModel):
    id: UUID
    approval_request_id: UUID
    action: ApprovalActionType
    reviewed_resource_version: str
    reason: str | None
    created_at: datetime
