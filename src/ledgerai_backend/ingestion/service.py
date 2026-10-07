"""Secure document and transaction ingestion orchestration."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePath
from time import perf_counter
from uuid import UUID, uuid4

from ledgerai_backend.core.errors import ApiError
from ledgerai_backend.core.observability import (
    csv_rows,
    dependency_failures,
    import_duration,
    scan_outcomes,
    upload_bytes,
    upload_operations,
)
from ledgerai_backend.core.request_context import AuthorizationContext
from ledgerai_backend.ingestion.csv_parser import CsvStructureError, parse_bank_csv
from ledgerai_backend.ingestion.models import (
    Document,
    DocumentScanResult,
    DocumentStatus,
    DocumentVersion,
    IdempotencyStatus,
    ImportStatus,
    ScanStatus,
    TransactionImport,
)
from ledgerai_backend.ingestion.repository import (
    IdempotencyConflict,
    IngestionRepository,
    canonical_fingerprint,
)
from ledgerai_backend.ingestion.schemas import (
    CsvColumnMapping,
    UploadCompleteRequest,
    UploadInitiateRequest,
    UploadInitiateResponse,
)
from ledgerai_backend.ports import (
    MalwareScannerPort,
    ObjectStoragePort,
    ScanOutcome,
    ScanResult,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext

MAGIC_TYPES = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)
EXTENSION_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def detect_media_type(content: bytes) -> str | None:
    for magic, media_type in MAGIC_TYPES:
        if content.startswith(magic):
            return media_type
    return None


def require_entity_context(context: AuthorizationContext) -> tuple[UUID, UUID]:
    if context.organization_id is None or context.legal_entity_id is None:
        raise ApiError(
            400,
            "INPUT_VALIDATION",
            "ENTITY_SCOPE_REQUIRED",
            "Organization and legal-entity scope are required.",
        )
    return context.organization_id, context.legal_entity_id


class IngestionService:
    def __init__(
        self,
        repository: IngestionRepository,
        context: AuthorizationContext,
        *,
        storage: ObjectStoragePort,
        scanner: MalwareScannerPort,
        scanner_timeout: float,
        upload_limit: int,
        presign_seconds: int,
        idempotency_ttl: int,
        csv_max_rows: int,
        csv_max_columns: int,
        csv_max_cell_chars: int,
    ) -> None:
        self.repository = repository
        self.context = context
        self.storage = storage
        self.scanner = scanner
        self.scanner_timeout = scanner_timeout
        self.upload_limit = upload_limit
        self.presign_seconds = presign_seconds
        self.idempotency_ttl = idempotency_ttl
        self.csv_max_rows = csv_max_rows
        self.csv_max_columns = csv_max_columns
        self.csv_max_cell_chars = csv_max_cell_chars

    async def initiate_upload(
        self, body: UploadInitiateRequest, *, idempotency_key: str
    ) -> UploadInitiateResponse:
        if body.byte_size > self.upload_limit:
            raise ApiError(413, "INPUT_VALIDATION", "UPLOAD_TOO_LARGE", "Upload is too large.")
        suffix = PurePath(body.original_filename).suffix.lower()
        if suffix in EXTENSION_TYPES and EXTENSION_TYPES[suffix] != body.media_type:
            raise ApiError(
                422,
                "INPUT_VALIDATION",
                "FILENAME_TYPE_MISMATCH",
                "Filename and declared media type do not match.",
            )
        fingerprint = canonical_fingerprint(body.model_dump(mode="json"))
        try:
            claim = await self.repository.claim_idempotency(
                actor_id=self.context.principal_id,
                operation="documents.upload.initiate",
                key=idempotency_key,
                fingerprint=fingerprint,
                correlation_id=UUID(self.context.correlation_id),
                ttl_seconds=self.idempotency_ttl,
            )
        except IdempotencyConflict as exc:
            raise ApiError(
                409,
                "CONFLICT",
                "IDEMPOTENCY_CONFLICT",
                "Idempotency key conflicts with another request.",
            ) from exc
        if claim.status == IdempotencyStatus.COMPLETED and claim.response_resource_id:
            version = await self.repository.get_version(claim.response_resource_id)
            if version:
                url = await asyncio.to_thread(
                    self.storage.create_upload_url,
                    object_key=version.object_key,
                    content_type=version.expected_media_type,
                    byte_size=version.expected_byte_size,
                    expires_seconds=self.presign_seconds,
                )
                return UploadInitiateResponse(
                    document_id=version.document_id,
                    upload_id=version.id,
                    upload_url=url,
                    expires_in_seconds=self.presign_seconds,
                    status=version.status,
                )

        document_id = body.document_id or uuid4()
        version_id = uuid4()
        object_key = f"quarantine/{self.context.tenant_id}/{document_id}/{version_id}"
        document = None
        version_number = 1
        if body.document_id:
            document = await self.repository.lock_document(body.document_id)
            if document is None:
                raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
            version_number = await self.repository.next_document_version(document_id)
            document.status = DocumentStatus.UPLOADING
        else:
            document = Document(
                id=document_id,
                tenant_id=self.repository.tenant_id,
                organization_id=self.repository.organization_id,
                legal_entity_id=self.repository.legal_entity_id,
                original_filename=body.original_filename,
                status=DocumentStatus.UPLOADING,
                created_by_principal_id=self.context.principal_id,
                correlation_id=UUID(self.context.correlation_id),
            )
        version = DocumentVersion(
            id=version_id,
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
            document_id=document_id,
            version_number=version_number,
            object_key=object_key,
            expected_media_type=body.media_type,
            expected_byte_size=body.byte_size,
            expected_sha256=body.sha256,
            status=DocumentStatus.UPLOADING,
        )
        self.repository.session.add_all((document, version))
        await self.repository.complete_idempotency(
            claim, resource_type="document_version", resource_id=version_id
        )
        url = await asyncio.to_thread(
            self.storage.create_upload_url,
            object_key=object_key,
            content_type=body.media_type,
            byte_size=body.byte_size,
            expires_seconds=self.presign_seconds,
        )
        upload_operations.add(1, {"operation": "initiate", "outcome": "accepted"})
        upload_bytes.add(body.byte_size, {"outcome": "expected"})
        return UploadInitiateResponse(
            document_id=document_id,
            upload_id=version_id,
            upload_url=url,
            expires_in_seconds=self.presign_seconds,
            status=version.status,
        )

    async def complete_upload(
        self, upload_id: UUID, body: UploadCompleteRequest, *, idempotency_key: str
    ) -> Document:
        fingerprint = canonical_fingerprint(
            {"upload_id": upload_id, **body.model_dump(mode="json")}
        )
        try:
            claim = await self.repository.claim_idempotency(
                actor_id=self.context.principal_id,
                operation="documents.upload.complete",
                key=idempotency_key,
                fingerprint=fingerprint,
                correlation_id=UUID(self.context.correlation_id),
                ttl_seconds=self.idempotency_ttl,
            )
        except IdempotencyConflict as exc:
            raise ApiError(
                409,
                "CONFLICT",
                "IDEMPOTENCY_CONFLICT",
                "Idempotency key conflicts with another request.",
            ) from exc
        version = await self.repository.lock_version(upload_id)
        if version is None:
            raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
        document = await self.repository.get_document(version.document_id)
        assert document is not None
        if version.status in {DocumentStatus.ACCEPTED, DocumentStatus.REJECTED}:
            await self.repository.complete_idempotency(
                claim, resource_type="document", resource_id=document.id
            )
            return document
        if body.sha256 != version.expected_sha256 or body.byte_size != version.expected_byte_size:
            version.status = document.status = DocumentStatus.FAILED
            version.failure_code = "UPLOAD_METADATA_MISMATCH"
            await self.repository.complete_idempotency(
                claim, resource_type="document", resource_id=document.id
            )
            return document
        try:
            stored = await asyncio.to_thread(
                self.storage.stat_object,
                object_key=version.object_key,
            )
            content = await asyncio.to_thread(
                self.storage.read_object,
                object_key=version.object_key,
                maximum_bytes=self.upload_limit,
            )
        except Exception:
            dependency_failures.add(1, {"dependency": "storage", "operation": "read"})
            version.status = document.status = DocumentStatus.FAILED
            version.failure_code = "STORAGE_OBJECT_UNAVAILABLE"
            await self.repository.fail_idempotency_transient(
                claim, resource_type="document", resource_id=document.id
            )
            return document
        if (
            stored.byte_size != version.expected_byte_size
            or stored.content_type != version.expected_media_type
            or (
                stored.server_side_encryption is not None
                and stored.server_side_encryption != "AES256"
            )
        ):
            version.status = document.status = DocumentStatus.FAILED
            version.failure_code = "UPLOAD_METADATA_MISMATCH"
            await self.repository.complete_idempotency(
                claim, resource_type="document", resource_id=document.id
            )
            return document
        version.storage_version = stored.version_id
        detected = detect_media_type(content)
        actual_hash = sha256(content).hexdigest()
        if (
            len(content) != version.expected_byte_size
            or actual_hash != version.expected_sha256
            or (stored.sha256 and stored.sha256 != actual_hash)
        ):
            version.status = document.status = DocumentStatus.FAILED
            version.failure_code = "UPLOAD_INTEGRITY_FAILED"
            await self.repository.complete_idempotency(
                claim, resource_type="document", resource_id=document.id
            )
            return document
        if detected is None or detected != version.expected_media_type:
            version.status = document.status = DocumentStatus.REJECTED
            version.failure_code = "UNSUPPORTED_CONTENT"
            await self.repository.complete_idempotency(
                claim, resource_type="document", resource_id=document.id
            )
            return document
        version.actual_byte_size = len(content)
        version.actual_sha256 = actual_hash
        version.detected_media_type = detected
        version.status = document.status = DocumentStatus.SCANNING
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self.scanner.scan, content, expected_sha256=actual_hash),
                timeout=self.scanner_timeout,
            )
        except TimeoutError:
            dependency_failures.add(1, {"dependency": "scanner", "operation": "scan"})
            result = ScanResult(
                ScanOutcome.TIMEOUT,
                "configured-scanner",
                "unknown",
                None,
                "SCAN_TIMEOUT",
            )
        except Exception:
            dependency_failures.add(1, {"dependency": "scanner", "operation": "scan"})
            result = ScanResult(
                ScanOutcome.ERROR,
                "configured-scanner",
                "unknown",
                None,
                "SCAN_UNAVAILABLE",
            )
        scan_outcomes.add(1, {"outcome": result.outcome.value})
        self.repository.session.add(
            DocumentScanResult(
                tenant_id=self.repository.tenant_id,
                organization_id=self.repository.organization_id,
                legal_entity_id=self.repository.legal_entity_id,
                document_version_id=version.id,
                content_sha256=actual_hash,
                result=ScanStatus(result.outcome.value),
                scanner_name=result.scanner_name,
                scanner_version=result.scanner_version,
                signature_version=result.signature_version,
                reason_code=result.reason_code,
            )
        )
        version.completed_at = datetime.now(UTC)
        if result.outcome == ScanOutcome.CLEAN:
            version.failure_code = None
            version.status = document.status = DocumentStatus.ACCEPTED
            self.repository.add_outbox(
                event_type="document.uploaded.v1",
                resource_type="document",
                resource_id=document.id,
                correlation_id=UUID(self.context.correlation_id),
            )
        elif result.outcome in {ScanOutcome.INFECTED, ScanOutcome.SUSPICIOUS}:
            version.status = document.status = DocumentStatus.REJECTED
            version.failure_code = result.reason_code
        else:
            version.status = document.status = DocumentStatus.QUARANTINED
            version.failure_code = result.reason_code
        outcome = version.status.value.lower()
        upload_operations.add(1, {"operation": "complete", "outcome": outcome})
        upload_bytes.add(len(content), {"outcome": outcome})
        if result.outcome in {
            ScanOutcome.UNAVAILABLE,
            ScanOutcome.ERROR,
            ScanOutcome.TIMEOUT,
        }:
            await self.repository.fail_idempotency_transient(
                claim, resource_type="document", resource_id=document.id
            )
        else:
            await self.repository.complete_idempotency(
                claim, resource_type="document", resource_id=document.id
            )
        return document

    async def import_csv(
        self,
        content: bytes,
        *,
        bank_account_id: UUID,
        mapping: CsvColumnMapping,
        idempotency_key: str,
    ) -> TransactionImport:
        started_at = perf_counter()
        source_hash = sha256(content).hexdigest()
        fingerprint = canonical_fingerprint(
            {
                "source_sha256": source_hash,
                "bank_account_id": bank_account_id,
                "mapping": mapping.model_dump(),
            }
        )
        try:
            claim = await self.repository.claim_idempotency(
                actor_id=self.context.principal_id,
                operation="transaction-imports.create",
                key=idempotency_key,
                fingerprint=fingerprint,
                correlation_id=UUID(self.context.correlation_id),
                ttl_seconds=self.idempotency_ttl,
            )
        except IdempotencyConflict as exc:
            raise ApiError(
                409,
                "CONFLICT",
                "IDEMPOTENCY_CONFLICT",
                "Idempotency key conflicts with another request.",
            ) from exc
        if claim.status == IdempotencyStatus.COMPLETED and claim.response_resource_id:
            existing = await self.repository.get_import(claim.response_resource_id)
            if existing:
                return existing
        existing = await self.repository.lock_and_find_import(
            source_sha256=source_hash, bank_account_id=bank_account_id
        )
        if existing:
            await self.repository.complete_idempotency(
                claim, resource_type="transaction_import", resource_id=existing.id
            )
            return existing
        import_id = uuid4()
        tenant_context = EntityTenantContext(
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
        )
        try:
            parsed = parse_bank_csv(
                content,
                mapping=mapping,
                maximum_rows=self.csv_max_rows,
                maximum_columns=self.csv_max_columns,
                maximum_cell_chars=self.csv_max_cell_chars,
                tenant_context=tenant_context,
                bank_account_id=bank_account_id,
                import_id=import_id,
                request_id=UUID(self.context.request_id),
                correlation_id=UUID(self.context.correlation_id),
            )
        except CsvStructureError as exc:
            raise ApiError(422, "INPUT_VALIDATION", exc.code, exc.safe_message) from exc
        import_row = TransactionImport(
            id=import_id,
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
            source_sha256=source_hash,
            bank_account_id=bank_account_id,
            status=ImportStatus.PROCESSING,
            created_by_principal_id=self.context.principal_id,
            correlation_id=UUID(self.context.correlation_id),
        )
        self.repository.session.add(import_row)
        await self.repository.session.flush()
        self.repository.store_import_rows(import_row, parsed)
        csv_rows.add(len(parsed.rows), {"outcome": "accepted"})
        csv_rows.add(len(parsed.errors), {"outcome": "rejected"})
        self.repository.add_outbox(
            event_type="transactions.imported.v1",
            resource_type="transaction_import",
            resource_id=import_id,
            correlation_id=UUID(self.context.correlation_id),
        )
        await self.repository.complete_idempotency(
            claim, resource_type="transaction_import", resource_id=import_id
        )
        await self.repository.session.flush()
        await self.repository.session.refresh(import_row)
        import_duration.record(perf_counter() - started_at, {"outcome": import_row.status.value})
        return import_row
