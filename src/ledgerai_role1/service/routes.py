"""API routes for Role 1 Document Intelligence."""

from __future__ import annotations

import base64
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ledgerai_contracts.v1.common import CorrelationMetadata
from ledgerai_contracts.v1.documents import DocumentExtraction, StorageReference
from ledgerai_role1.ontology.schema import to_contract_extraction
from ledgerai_role1.pipeline.pretrained_baseline import PretrainedDocumentExtractor
from ledgerai_role1.service.idempotency import ExtractionIdempotencyStore
from ledgerai_role1.service.limits import verify_file_signature_and_limits
from ledgerai_role1.service.security import (
    AuthenticatedRoleContext,
    authenticate_service_request,
    validate_object_reference,
)

router = APIRouter()
AuthContext = Annotated[AuthenticatedRoleContext, Depends(authenticate_service_request)]


class ExtractionRequestPayload(BaseModel):
    """Payload sent by Role 4 to request document extraction."""

    model_config = ConfigDict(extra="ignore")

    operation_id: UUID | None = None
    tenant_context: Any | None = None
    document_id: UUID = Field(default_factory=uuid4)
    document_version: str = Field(default="1", min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    storage_reference: StorageReference | None = None
    media_type: str = Field(default="text/plain", pattern=r"^[\w.+-]+/[\w.+-]+$")
    document_content_base64: str | None = None
    document_text: str | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_version(cls, data: Any) -> Any:
        if (
            isinstance(data, dict)
            and "document_version" not in data
            and "document_version_id" in data
        ):
            data["document_version"] = str(data["document_version_id"])
        return data


@router.post(
    "/v1/extractions",
    response_model=DocumentExtraction,
    response_model_exclude_none=False,
    status_code=status.HTTP_200_OK,
)
async def request_extraction(
    payload: ExtractionRequestPayload,
    request: Request,
    auth: AuthContext,
) -> DocumentExtraction:
    """Execute document intelligence extraction for Role 4."""
    # Verify operation binding and tenant context if provided in payload
    if payload.operation_id is not None and payload.operation_id != auth.operation_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payload operation ID does not match authenticated token operation ID",
        )
    if payload.tenant_context is not None:
        t_id = (
            payload.tenant_context.get("tenant_id")
            if isinstance(payload.tenant_context, dict)
            else getattr(payload.tenant_context, "tenant_id", None)
        )
        if t_id is not None and str(t_id) != str(auth.tenant_context.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Payload tenant context does not match authenticated token context",
            )

    idempotency_store: ExtractionIdempotencyStore = request.app.state.idempotency_store
    extractor: PretrainedDocumentExtractor = request.app.state.extractor
    settings = request.app.state.settings

    # Idempotency check
    cached = idempotency_store.get(auth.tenant_context.tenant_id, auth.operation_id)
    if cached is not None:
        return cached

    # Resolve document content bytes
    doc_bytes: bytes
    if payload.document_content_base64:
        try:
            doc_bytes = base64.b64decode(payload.document_content_base64)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malformed base64 document content: {e}",
            ) from e
    elif payload.document_text:
        doc_bytes = payload.document_text.encode()
    elif payload.storage_reference:
        validate_object_reference(
            payload.storage_reference.object_key,
            settings.allowlisted_storage_prefix,
        )
        storage_loader = getattr(request.app.state, "storage_loader", None)
        if storage_loader:
            doc_bytes = storage_loader(payload.storage_reference.object_key)
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage loader is unavailable to fetch referenced document",
            )
    else:
        storage_loader = getattr(request.app.state, "storage_loader", None)
        if storage_loader:
            doc_bytes = storage_loader(f"documents/{payload.document_id}")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No document content or valid storage reference provided",
            )

    # Verify signature, limits, and decompression safety
    verify_file_signature_and_limits(
        doc_bytes,
        payload.media_type,
        max_bytes=settings.max_request_bytes,
        max_pages=settings.max_page_count,
    )

    # Perform extraction
    canonical_data = extractor.extract(doc_bytes, media_type=payload.media_type)

    # Convert to strict DocumentExtraction contract
    correlation = CorrelationMetadata(
        request_id=auth.operation_id,
        correlation_id=auth.correlation_id,
        causation_id=auth.causation_id,
    )

    contract = to_contract_extraction(
        canonical_data,
        extraction_id=uuid4(),
        document_id=payload.document_id,
        document_version=payload.document_version,
        tenant_context=auth.tenant_context,
        correlation=correlation,
        producer=extractor.get_producer_metadata(),
    )

    idempotency_store.set(auth.tenant_context.tenant_id, auth.operation_id, contract)
    return contract


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/health/ready")
async def health_ready() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/metrics")
async def metrics(auth: AuthContext) -> dict[str, Any]:
    return {
        "service": "role1-document-intelligence",
        "status": "healthy",
        "version": "1.0.0",
        "ontology_version": "1.0.0",
    }
