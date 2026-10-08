"""Authenticated Phase 4 assurance, accounting, audit, and progress APIs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query, Request
from starlette.responses import StreamingResponse

from ledgerai_backend.api.dependencies import RequestScope, authorized_scope
from ledgerai_backend.assurance.repository import AssuranceRepository
from ledgerai_backend.assurance.schemas import (
    AccountingPeriodCreate,
    AccountingPeriodResponse,
    AuditEventResponse,
    CloseRunResponse,
    PostingConfirmationResponse,
    PostingOperationCreate,
    PostingOperationResponse,
    ProgressEventResponse,
    ProgressProjectionResponse,
    ProvenanceTraceResponse,
    StatementLineResponse,
    StatementSnapshotResponse,
)
from ledgerai_backend.assurance.service import AssuranceService
from ledgerai_backend.core.errors import ERROR_RESPONSES, ApiError
from ledgerai_backend.ingestion.service import require_entity_context
from ledgerai_backend.tenancy.permissions import PermissionCode, require_permission

router = APIRouter(responses=ERROR_RESPONSES)
Scope = Annotated[RequestScope, Depends(authorized_scope)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$"),
]


def _repository(scope: RequestScope) -> AssuranceRepository:
    organization_id, legal_entity_id = require_entity_context(scope.context)
    return AssuranceRepository(
        scope.session, scope.context.tenant_id, organization_id, legal_entity_id
    )


def _service(request: Request, scope: RequestScope) -> AssuranceService:
    role2 = request.app.state.role_adapters.get("role2")
    return AssuranceService(_repository(scope), scope.context, role2)


async def _posting_response(
    repository: AssuranceRepository, operation: object
) -> PostingOperationResponse:
    response = PostingOperationResponse.model_validate(operation)
    confirmation = await repository.confirmation(response.operation_id)
    if confirmation is not None:
        response.confirmation = PostingConfirmationResponse.model_validate(confirmation)
    return response


@router.post("/accounting-periods", response_model=AccountingPeriodResponse, status_code=201)
async def create_accounting_period(
    body: AccountingPeriodCreate, request: Request, scope: Scope
) -> AccountingPeriodResponse:
    require_permission(scope.context, PermissionCode.PERIOD_CLOSE_REQUEST)
    row = await _service(request, scope).create_period(body)
    return AccountingPeriodResponse.model_validate(row)


@router.get("/accounting-periods", response_model=list[AccountingPeriodResponse])
async def list_accounting_periods(
    scope: Scope, limit: Annotated[int, Query(ge=1, le=100)] = 100
) -> list[AccountingPeriodResponse]:
    require_permission(scope.context, PermissionCode.FINANCIAL_STATEMENT_READ)
    rows = await _repository(scope).list_periods(limit=limit)
    return [AccountingPeriodResponse.model_validate(row) for row in rows]


@router.post("/posting-operations", response_model=PostingOperationResponse, status_code=202)
async def start_posting(
    body: PostingOperationCreate,
    request: Request,
    scope: Scope,
    idempotency_key: IdempotencyKey,
) -> PostingOperationResponse:
    require_permission(scope.context, PermissionCode.POSTING_EXECUTE)
    service = _service(request, scope)
    row = await service.start_posting(body, idempotency_key=idempotency_key)
    return await _posting_response(service.repository, row)


@router.get("/posting-operations/{operation_id}", response_model=PostingOperationResponse)
async def get_posting(operation_id: UUID, scope: Scope) -> PostingOperationResponse:
    require_permission(scope.context, PermissionCode.REVIEW_READ)
    repository = _repository(scope)
    row = await repository.posting(operation_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return await _posting_response(repository, row)


@router.post("/posting-operations/{operation_id}/recover", response_model=PostingOperationResponse)
async def recover_posting(
    operation_id: UUID, request: Request, scope: Scope
) -> PostingOperationResponse:
    require_permission(scope.context, PermissionCode.POSTING_EXECUTE)
    service = _service(request, scope)
    row = await service.refresh_posting(operation_id)
    return await _posting_response(service.repository, row)


@router.post(
    "/accounting-periods/{period_id}/close", response_model=CloseRunResponse, status_code=202
)
async def close_period(
    period_id: UUID,
    request: Request,
    scope: Scope,
    idempotency_key: IdempotencyKey,
) -> CloseRunResponse:
    require_permission(scope.context, PermissionCode.PERIOD_CLOSE_REQUEST)
    row = await _service(request, scope).start_close(period_id, idempotency_key=idempotency_key)
    return CloseRunResponse.model_validate(row)


@router.post("/period-close-operations/{operation_id}/recover", response_model=CloseRunResponse)
async def recover_close(operation_id: UUID, request: Request, scope: Scope) -> CloseRunResponse:
    require_permission(scope.context, PermissionCode.PERIOD_CLOSE_REQUEST)
    row = await _service(request, scope).refresh_close(operation_id)
    return CloseRunResponse.model_validate(row)


@router.post(
    "/accounting-periods/{period_id}/statements/{statement_type}",
    response_model=StatementSnapshotResponse,
    status_code=201,
)
async def capture_statement(
    period_id: UUID,
    statement_type: Literal["TRIAL_BALANCE", "PROFIT_AND_LOSS", "BALANCE_SHEET"],
    request: Request,
    scope: Scope,
) -> StatementSnapshotResponse:
    require_permission(scope.context, PermissionCode.FINANCIAL_STATEMENT_READ)
    service = _service(request, scope)
    row = await service.request_statement(period_id, statement_type)
    lines = await service.repository.statement_lines(row.id)
    return StatementSnapshotResponse(
        id=row.id,
        role2_snapshot_id=row.role2_snapshot_id,
        accounting_period_id=row.accounting_period_id,
        statement_type=row.statement_type,  # type: ignore[arg-type]
        currency=row.currency,
        as_of=row.as_of,
        role2_version=row.role2_version,
        created_at=row.created_at,
        lines=[
            StatementLineResponse(
                line_id=line.line_key,
                account_reference=line.account_reference,
                label=line.label,
                amount=line.amount,
                currency=line.currency,
                ledger_references=line.ledger_references,
            )
            for line in lines
        ],
    )


@router.get("/financial-statements/{snapshot_id}", response_model=StatementSnapshotResponse)
async def get_statement(snapshot_id: UUID, scope: Scope) -> StatementSnapshotResponse:
    require_permission(scope.context, PermissionCode.FINANCIAL_STATEMENT_READ)
    repository = _repository(scope)
    row = await repository.statement(snapshot_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    lines = await repository.statement_lines(row.id)
    return StatementSnapshotResponse(
        id=row.id,
        role2_snapshot_id=row.role2_snapshot_id,
        accounting_period_id=row.accounting_period_id,
        statement_type=row.statement_type,  # type: ignore[arg-type]
        currency=row.currency,
        as_of=row.as_of,
        role2_version=row.role2_version,
        created_at=row.created_at,
        lines=[
            StatementLineResponse(
                line_id=line.line_key,
                account_reference=line.account_reference,
                label=line.label,
                amount=line.amount,
                currency=line.currency,
                ledger_references=line.ledger_references,
            )
            for line in lines
        ],
    )


@router.get("/audit-events", response_model=list[AuditEventResponse])
async def list_audit_events(
    scope: Scope,
    resource_type: Annotated[str | None, Query(max_length=100)] = None,
    resource_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[AuditEventResponse]:
    require_permission(scope.context, PermissionCode.AUDIT_READ)
    rows = await _repository(scope).list_audit(
        resource_type=resource_type, resource_id=resource_id, limit=limit
    )
    return [AuditEventResponse.model_validate(row) for row in rows]


@router.get("/provenance/{resource_type}/{resource_id}", response_model=ProvenanceTraceResponse)
async def provenance_trace(
    resource_type: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{0,99}$")],
    resource_id: UUID,
    request: Request,
    scope: Scope,
) -> ProvenanceTraceResponse:
    require_permission(scope.context, PermissionCode.AUDIT_READ)
    return await _service(request, scope).trace(resource_type, resource_id)


@router.get("/progress/{resource_type}/{resource_id}", response_model=ProgressProjectionResponse)
async def get_progress(
    resource_type: str, resource_id: UUID, scope: Scope
) -> ProgressProjectionResponse:
    require_permission(scope.context, PermissionCode.PROGRESS_READ)
    row = await _repository(scope).projection(resource_type, resource_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return ProgressProjectionResponse.model_validate(row)


@router.get("/progress-stream")
async def progress_stream(
    request: Request,
    scope: Scope,
    last_event_id: Annotated[UUID | None, Header(alias="Last-Event-ID")] = None,
    once: bool = False,
) -> StreamingResponse:
    """Replay tenant events after Last-Event-ID, then follow with heartbeats."""
    require_permission(scope.context, PermissionCode.PROGRESS_READ)
    repository = _repository(scope)
    if last_event_id is not None and not await repository.has_progress_event(last_event_id):
        raise ApiError(
            409,
            "CONFLICT",
            "PROGRESS_CURSOR_UNKNOWN",
            "The progress resume cursor is unavailable.",
        )

    async def events() -> AsyncIterator[str]:
        cursor = last_event_id
        while True:
            rows = await repository.progress_after(cursor, limit=100)
            for row in rows:
                payload = ProgressEventResponse.model_validate(row).model_dump(mode="json")
                yield (
                    f"id: {row.progress_event_id}\n"
                    "event: progress\n"
                    f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
                )
                cursor = row.progress_event_id
            if once:
                return
            if await request.is_disconnected():
                return
            if not rows:
                yield ": heartbeat\n\n"
            await asyncio.sleep(15)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
