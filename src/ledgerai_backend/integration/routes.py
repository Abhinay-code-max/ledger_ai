"""Tenant-scoped Phase 3 evidence and human-review APIs."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from ledgerai_backend.api.dependencies import RequestScope, authorized_scope
from ledgerai_backend.core.errors import ERROR_RESPONSES, ApiError
from ledgerai_backend.ingestion.service import require_entity_context
from ledgerai_backend.integration.models import (
    ApprovalActionType,
    ApprovalRequest,
    ApprovalStatus,
    ExceptionResolution,
    ExceptionSeverity,
    JournalProposal,
    MatchProposal,
    WorkflowException,
)
from ledgerai_backend.integration.repository import IntegrationRepository
from ledgerai_backend.integration.schemas import (
    ApprovalActionRequest,
    ApprovalActionResponse,
    ApprovalRequestResponse,
    ExceptionResponse,
    JournalProposalResponse,
    MatchProposalResponse,
    Page,
)
from ledgerai_backend.integration.service import ApprovalService
from ledgerai_backend.tenancy.permissions import PermissionCode, require_permission

router = APIRouter(responses=ERROR_RESPONSES)
Scope = Annotated[RequestScope, Depends(authorized_scope)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$"),
]
ExpectedVersion = Annotated[int, Header(alias="If-Match", ge=1)]


def _repository(scope: RequestScope) -> IntegrationRepository:
    organization_id, legal_entity_id = require_entity_context(scope.context)
    return IntegrationRepository(
        scope.session, scope.context.tenant_id, organization_id, legal_entity_id
    )


def _page(rows: list[Any], limit: int, schema: type[BaseModel]) -> Page:
    has_more = len(rows) > limit
    items = rows[:limit]
    return Page(
        items=[schema.model_validate(row) for row in items],
        next_cursor=items[-1].id if has_more else None,
    )


@router.get("/exceptions", response_model=Page)
async def list_exceptions(
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
    severity: ExceptionSeverity | None = None,
    status: ExceptionResolution | None = None,
) -> Page:
    require_permission(scope.context, PermissionCode.EXCEPTION_READ)
    filters: list[object] = []
    if severity:
        filters.append(WorkflowException.severity == severity)
    if status:
        filters.append(WorkflowException.resolution_status == status)
    rows = await _repository(scope).list_rows(
        WorkflowException, limit=limit, after=after, filters=tuple(filters)
    )
    return _page(rows, limit, ExceptionResponse)


@router.get("/exceptions/{exception_id}", response_model=ExceptionResponse)
async def get_exception(exception_id: UUID, scope: Scope) -> ExceptionResponse:
    require_permission(scope.context, PermissionCode.EXCEPTION_READ)
    row = await _repository(scope).get(WorkflowException, exception_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return ExceptionResponse.model_validate(row)


@router.get("/reconciliation-proposals", response_model=Page)
async def list_reconciliation_proposals(
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
) -> Page:
    require_permission(scope.context, PermissionCode.RECONCILIATION_READ)
    rows = await _repository(scope).list_rows(MatchProposal, limit=limit, after=after)
    return _page(rows, limit, MatchProposalResponse)


@router.get("/reconciliation-proposals/{proposal_id}", response_model=MatchProposalResponse)
async def get_reconciliation_proposal(proposal_id: UUID, scope: Scope) -> MatchProposalResponse:
    require_permission(scope.context, PermissionCode.RECONCILIATION_READ)
    row = await _repository(scope).get(MatchProposal, proposal_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return MatchProposalResponse.model_validate(row)


@router.get("/journal-proposals/{proposal_id}", response_model=JournalProposalResponse)
async def get_journal_proposal(proposal_id: UUID, scope: Scope) -> JournalProposalResponse:
    require_permission(scope.context, PermissionCode.REVIEW_READ)
    row = await _repository(scope).get(JournalProposal, proposal_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return JournalProposalResponse.model_validate(row)


@router.get("/approval-requests", response_model=Page)
async def list_approval_requests(
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
    status: ApprovalStatus | None = None,
) -> Page:
    require_permission(scope.context, PermissionCode.REVIEW_READ)
    filters = (ApprovalRequest.status == status,) if status else ()
    rows = await _repository(scope).list_rows(
        ApprovalRequest, limit=limit, after=after, filters=filters
    )
    return _page(rows, limit, ApprovalRequestResponse)


@router.get("/approval-requests/{request_id}", response_model=ApprovalRequestResponse)
async def get_approval_request(request_id: UUID, scope: Scope) -> ApprovalRequestResponse:
    require_permission(scope.context, PermissionCode.REVIEW_READ)
    row = await _repository(scope).get(ApprovalRequest, request_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return ApprovalRequestResponse.model_validate(row)


async def _action(
    request_id: UUID,
    action: ApprovalActionType,
    body: ApprovalActionRequest,
    scope: RequestScope,
    idempotency_key: str,
    expected_version: int,
    permission: PermissionCode,
) -> ApprovalActionResponse:
    require_permission(scope.context, permission)
    row = await ApprovalService(_repository(scope), scope.context).act(
        request_id, action, body, idempotency_key=idempotency_key, expected_version=expected_version
    )
    return ApprovalActionResponse.model_validate(row)


@router.post("/approval-requests/{request_id}/approve", response_model=ApprovalActionResponse)
async def approve(
    request_id: UUID,
    body: ApprovalActionRequest,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    expected_version: ExpectedVersion,
) -> ApprovalActionResponse:
    return await _action(
        request_id,
        ApprovalActionType.APPROVE,
        body,
        scope,
        idempotency_key,
        expected_version,
        PermissionCode.REVIEW_APPROVE,
    )


@router.post("/approval-requests/{request_id}/correct", response_model=ApprovalActionResponse)
async def correct(
    request_id: UUID,
    body: ApprovalActionRequest,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    expected_version: ExpectedVersion,
) -> ApprovalActionResponse:
    return await _action(
        request_id,
        ApprovalActionType.CORRECT,
        body,
        scope,
        idempotency_key,
        expected_version,
        PermissionCode.REVIEW_CORRECT,
    )


@router.post("/approval-requests/{request_id}/reject", response_model=ApprovalActionResponse)
async def reject(
    request_id: UUID,
    body: ApprovalActionRequest,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    expected_version: ExpectedVersion,
) -> ApprovalActionResponse:
    return await _action(
        request_id,
        ApprovalActionType.REJECT,
        body,
        scope,
        idempotency_key,
        expected_version,
        PermissionCode.REVIEW_REJECT,
    )


@router.post(
    "/approval-requests/{request_id}/request-evidence", response_model=ApprovalActionResponse
)
async def request_evidence(
    request_id: UUID,
    body: ApprovalActionRequest,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    expected_version: ExpectedVersion,
) -> ApprovalActionResponse:
    return await _action(
        request_id,
        ApprovalActionType.REQUEST_EVIDENCE,
        body,
        scope,
        idempotency_key,
        expected_version,
        PermissionCode.REVIEW_REQUEST_EVIDENCE,
    )


@router.post("/approval-requests/{request_id}/escalate", response_model=ApprovalActionResponse)
async def escalate(
    request_id: UUID,
    body: ApprovalActionRequest,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    expected_version: ExpectedVersion,
) -> ApprovalActionResponse:
    return await _action(
        request_id,
        ApprovalActionType.ESCALATE,
        body,
        scope,
        idempotency_key,
        expected_version,
        PermissionCode.REVIEW_ESCALATE,
    )
