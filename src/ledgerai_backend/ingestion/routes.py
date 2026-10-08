"""Tenant-scoped Phase 2 document, import, transaction, and job APIs."""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile
from pydantic import ValidationError

from ledgerai_backend.api.dependencies import RequestScope, authorized_scope
from ledgerai_backend.core.errors import ERROR_RESPONSES, ApiError
from ledgerai_backend.ingestion.models import JobStatus
from ledgerai_backend.ingestion.repository import IngestionRepository
from ledgerai_backend.ingestion.schemas import (
    BankTransactionList,
    BankTransactionResponse,
    CsvColumnMapping,
    DocumentList,
    DocumentResponse,
    DocumentVersionResponse,
    ImportErrorResponse,
    JobResponse,
    TransactionImportResponse,
    UploadCompleteRequest,
    UploadInitiateRequest,
    UploadInitiateResponse,
)
from ledgerai_backend.ingestion.service import IngestionService, require_entity_context
from ledgerai_backend.tenancy.permissions import PermissionCode, require_permission
from ledgerai_backend.workflow.reliability import transition_job

router = APIRouter(responses=ERROR_RESPONSES)
Scope = Annotated[RequestScope, Depends(authorized_scope)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$"),
]


def _repository(scope: RequestScope) -> IngestionRepository:
    organization_id, legal_entity_id = require_entity_context(scope.context)
    return IngestionRepository(
        scope.session, scope.context.tenant_id, organization_id, legal_entity_id
    )


def _service(request: Request, scope: RequestScope) -> IngestionService:
    storage = request.app.state.object_storage
    scanner = request.app.state.malware_scanner
    if storage is None or scanner is None:
        raise ApiError(
            503,
            "DOWNSTREAM",
            "INGESTION_DEPENDENCY_UNAVAILABLE",
            "Ingestion dependencies are unavailable.",
        )
    settings = request.app.state.settings
    return IngestionService(
        _repository(scope),
        scope.context,
        storage=storage,
        scanner=scanner,
        scanner_timeout=settings.scanner_timeout_seconds,
        upload_limit=settings.storage_max_upload_bytes,
        presign_seconds=settings.storage_presign_seconds,
        idempotency_ttl=settings.idempotency_ttl_seconds,
        csv_max_rows=settings.csv_max_rows,
        csv_max_columns=settings.csv_max_columns,
        csv_max_cell_chars=settings.csv_max_cell_chars,
    )


@router.post("/documents/uploads", response_model=UploadInitiateResponse, status_code=201)
async def initiate_document_upload(
    body: UploadInitiateRequest,
    request: Request,
    scope: Scope,
    idempotency_key: IdempotencyKey,
) -> UploadInitiateResponse:
    require_permission(scope.context, PermissionCode.DOCUMENT_WRITE)
    return await _service(request, scope).initiate_upload(body, idempotency_key=idempotency_key)


@router.post("/documents/uploads/{upload_id}/complete", response_model=DocumentResponse)
async def complete_document_upload(
    upload_id: UUID,
    body: UploadCompleteRequest,
    request: Request,
    scope: Scope,
    idempotency_key: IdempotencyKey,
) -> DocumentResponse:
    require_permission(scope.context, PermissionCode.DOCUMENT_WRITE)
    document = await _service(request, scope).complete_upload(
        upload_id, body, idempotency_key=idempotency_key
    )
    return DocumentResponse.model_validate(document)


@router.get("/documents", response_model=DocumentList)
async def list_documents(
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
) -> DocumentList:
    require_permission(scope.context, PermissionCode.DOCUMENT_READ)
    rows = await _repository(scope).list_documents(limit=limit, after=after)
    has_more = len(rows) > limit
    items = rows[:limit]
    return DocumentList(
        items=[DocumentResponse.model_validate(row) for row in items],
        next_cursor=items[-1].id if has_more else None,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: UUID, scope: Scope) -> DocumentResponse:
    require_permission(scope.context, PermissionCode.DOCUMENT_READ)
    row = await _repository(scope).get_document(document_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return DocumentResponse.model_validate(row)


@router.get("/documents/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def get_document_versions(document_id: UUID, scope: Scope) -> list[DocumentVersionResponse]:
    require_permission(scope.context, PermissionCode.DOCUMENT_READ)
    repository = _repository(scope)
    if await repository.get_document(document_id) is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return [
        DocumentVersionResponse.model_validate(row)
        for row in await repository.list_document_versions(document_id)
    ]


@router.post("/transaction-imports", response_model=TransactionImportResponse, status_code=201)
async def create_transaction_import(
    request: Request,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    bank_account_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
    mapping_json: Annotated[str, Form(max_length=2_000)] = "{}",
) -> TransactionImportResponse:
    require_permission(scope.context, PermissionCode.DOCUMENT_WRITE)
    if file.content_type not in {"text/csv", "application/csv", "text/plain"}:
        raise ApiError(
            415, "INPUT_VALIDATION", "UNSUPPORTED_CONTENT", "Only CSV content is accepted."
        )
    settings = request.app.state.settings
    content = await file.read(settings.max_request_bytes + 1)
    if len(content) > settings.max_request_bytes:
        raise ApiError(413, "INPUT_VALIDATION", "REQUEST_TOO_LARGE", "The request is too large.")
    try:
        mapping = CsvColumnMapping.model_validate(json.loads(mapping_json))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ApiError(
            422, "INPUT_VALIDATION", "INVALID_COLUMN_MAPPING", "Column mapping is invalid."
        ) from exc
    row = await _service(request, scope).import_csv(
        content,
        bank_account_id=bank_account_id,
        mapping=mapping,
        idempotency_key=idempotency_key,
    )
    return TransactionImportResponse.model_validate(row)


@router.get("/transaction-imports/{import_id}", response_model=TransactionImportResponse)
async def get_transaction_import(import_id: UUID, scope: Scope) -> TransactionImportResponse:
    require_permission(scope.context, PermissionCode.DOCUMENT_READ)
    row = await _repository(scope).get_import(import_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return TransactionImportResponse.model_validate(row)


@router.get("/transaction-imports/{import_id}/errors", response_model=list[ImportErrorResponse])
async def get_transaction_import_errors(
    import_id: UUID,
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ImportErrorResponse]:
    require_permission(scope.context, PermissionCode.DOCUMENT_READ)
    repository = _repository(scope)
    if await repository.get_import(import_id) is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return [
        ImportErrorResponse.model_validate(row)
        for row in await repository.import_errors(import_id, limit=limit)
    ]


@router.get("/transactions", response_model=BankTransactionList)
async def list_transactions(
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
    import_id: UUID | None = None,
) -> BankTransactionList:
    require_permission(scope.context, PermissionCode.FINANCIAL_STATEMENT_READ)
    repository = _repository(scope)
    if import_id is not None and await repository.get_import(import_id) is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    rows = await repository.list_transactions(limit=limit, after=after, import_id=import_id)
    has_more = len(rows) > limit
    items = rows[:limit]
    return BankTransactionList(
        items=[BankTransactionResponse.model_validate(row) for row in items],
        next_cursor=items[-1].id if has_more else None,
    )


@router.get("/transactions/{transaction_id}", response_model=BankTransactionResponse)
async def get_transaction(transaction_id: UUID, scope: Scope) -> BankTransactionResponse:
    require_permission(scope.context, PermissionCode.FINANCIAL_STATEMENT_READ)
    row = await _repository(scope).get_transaction(transaction_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return BankTransactionResponse.model_validate(row)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, scope: Scope) -> JobResponse:
    require_permission(scope.context, PermissionCode.WORKSPACE_READ)
    row = await _repository(scope).get_job(job_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return JobResponse.model_validate(row)


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: UUID,
    scope: Scope,
    expected_version: Annotated[int, Header(alias="If-Match", ge=1)],
) -> JobResponse:
    require_permission(scope.context, PermissionCode.DOCUMENT_WRITE)
    row = await _repository(scope).get_job(job_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    if (
        row.status != JobStatus.FAILED
        or row.retryable is not True
        or row.attempt_number >= row.maximum_attempts
    ):
        raise ApiError(409, "CONFLICT", "JOB_NOT_RETRYABLE", "The job cannot be retried.")
    try:
        transition_job(row, JobStatus.QUEUED, expected_version=expected_version)
    except ValueError as exc:
        raise ApiError(
            409, "CONFLICT", "STALE_OR_ILLEGAL_TRANSITION", "The job state changed."
        ) from exc
    row.error_code = None
    row.safe_error_message = None
    row.failed_at = None
    row.retryable = None
    return JobResponse.model_validate(row)
