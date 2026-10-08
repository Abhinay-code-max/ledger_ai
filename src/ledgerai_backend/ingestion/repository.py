"""Tenant-explicit persistence for ingestion and workflow resources."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ledgerai_backend.ingestion.csv_parser import CsvParseResult
from ledgerai_backend.ingestion.models import (
    BankTransaction,
    DeliveryStatus,
    Document,
    DocumentVersion,
    IdempotencyRecord,
    IdempotencyStatus,
    ImportStatus,
    OutboxEvent,
    ProcessingJob,
    TransactionImport,
    TransactionImportError,
)
from ledgerai_backend.ingestion.schemas import ParsedTransaction
from ledgerai_contracts.v1.common import ResourceReference
from ledgerai_contracts.v1.events import EVENT_REGISTRY


def canonical_fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(encoded).hexdigest()


class IdempotencyConflict(Exception):
    pass


class IngestionRepository:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        organization_id: UUID,
        legal_entity_id: UUID,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.organization_id = organization_id
        self.legal_entity_id = legal_entity_id

    async def claim_idempotency(
        self,
        *,
        actor_id: UUID,
        operation: str,
        key: str,
        fingerprint: str,
        correlation_id: UUID,
        ttl_seconds: int,
    ) -> IdempotencyRecord:
        record_id = uuid4()
        statement = (
            insert(IdempotencyRecord)
            .values(
                id=record_id,
                tenant_id=self.tenant_id,
                organization_id=self.organization_id,
                legal_entity_id=self.legal_entity_id,
                actor_id=actor_id,
                operation=operation,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                status=IdempotencyStatus.IN_PROGRESS,
                correlation_id=correlation_id,
                expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            )
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "actor_id", "operation", "idempotency_key"]
            )
            .returning(IdempotencyRecord.id)
        )
        inserted = await self.session.scalar(statement)
        query = (
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.tenant_id == self.tenant_id,
                IdempotencyRecord.actor_id == actor_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.idempotency_key == key,
            )
            .with_for_update()
        )
        record = await self.session.scalar(query)
        assert record is not None
        if inserted is None and record.expires_at <= datetime.now(UTC):
            record.request_fingerprint = fingerprint
            record.status = IdempotencyStatus.IN_PROGRESS
            record.response_resource_type = None
            record.response_resource_id = None
            record.correlation_id = correlation_id
            record.expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
            return record
        if inserted is None and record.request_fingerprint != fingerprint:
            raise IdempotencyConflict
        return record

    async def complete_idempotency(
        self, record: IdempotencyRecord, *, resource_type: str, resource_id: UUID
    ) -> None:
        record.status = IdempotencyStatus.COMPLETED
        record.response_resource_type = resource_type
        record.response_resource_id = resource_id

    async def fail_idempotency_transient(
        self, record: IdempotencyRecord, *, resource_type: str, resource_id: UUID
    ) -> None:
        record.status = IdempotencyStatus.TRANSIENT_FAILURE
        record.response_resource_type = resource_type
        record.response_resource_id = resource_id

    async def delete_expired_idempotency(self, *, batch_size: int = 500) -> int:
        expired_ids = list(
            await self.session.scalars(
                select(IdempotencyRecord.id)
                .where(
                    IdempotencyRecord.tenant_id == self.tenant_id,
                    IdempotencyRecord.expires_at < datetime.now(UTC),
                    IdempotencyRecord.status != IdempotencyStatus.IN_PROGRESS,
                )
                .order_by(IdempotencyRecord.expires_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        if expired_ids:
            await self.session.execute(
                delete(IdempotencyRecord).where(IdempotencyRecord.id.in_(expired_ids))
            )
        return len(expired_ids)

    async def get_document(self, document_id: UUID) -> Document | None:
        return await self.session.scalar(
            select(Document).where(
                Document.tenant_id == self.tenant_id,
                Document.organization_id == self.organization_id,
                Document.legal_entity_id == self.legal_entity_id,
                Document.id == document_id,
            )
        )

    async def lock_document(self, document_id: UUID) -> Document | None:
        return await self.session.scalar(
            select(Document)
            .where(
                Document.tenant_id == self.tenant_id,
                Document.organization_id == self.organization_id,
                Document.legal_entity_id == self.legal_entity_id,
                Document.id == document_id,
            )
            .with_for_update()
        )

    async def next_document_version(self, document_id: UUID) -> int:
        current = await self.session.scalar(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.tenant_id == self.tenant_id,
                DocumentVersion.document_id == document_id,
            )
        )
        return int(current or 0) + 1

    async def list_documents(self, *, limit: int, after: UUID | None) -> list[Document]:
        query = select(Document).where(
            Document.tenant_id == self.tenant_id,
            Document.organization_id == self.organization_id,
            Document.legal_entity_id == self.legal_entity_id,
        )
        if after:
            query = query.where(Document.id > after)
        return list(await self.session.scalars(query.order_by(Document.id).limit(limit + 1)))

    async def list_document_versions(self, document_id: UUID) -> list[DocumentVersion]:
        return list(
            await self.session.scalars(
                select(DocumentVersion)
                .where(
                    DocumentVersion.tenant_id == self.tenant_id,
                    DocumentVersion.document_id == document_id,
                )
                .order_by(DocumentVersion.version_number)
            )
        )

    async def get_version(self, version_id: UUID) -> DocumentVersion | None:
        return await self.session.scalar(
            select(DocumentVersion).where(
                DocumentVersion.tenant_id == self.tenant_id,
                DocumentVersion.organization_id == self.organization_id,
                DocumentVersion.legal_entity_id == self.legal_entity_id,
                DocumentVersion.id == version_id,
            )
        )

    async def lock_version(self, version_id: UUID) -> DocumentVersion | None:
        return await self.session.scalar(
            select(DocumentVersion)
            .where(
                DocumentVersion.tenant_id == self.tenant_id,
                DocumentVersion.organization_id == self.organization_id,
                DocumentVersion.legal_entity_id == self.legal_entity_id,
                DocumentVersion.id == version_id,
            )
            .with_for_update()
        )

    async def get_import(self, import_id: UUID) -> TransactionImport | None:
        return await self.session.scalar(
            select(TransactionImport).where(
                TransactionImport.tenant_id == self.tenant_id,
                TransactionImport.organization_id == self.organization_id,
                TransactionImport.legal_entity_id == self.legal_entity_id,
                TransactionImport.id == import_id,
            )
        )

    async def lock_and_find_import(
        self, *, source_sha256: str, bank_account_id: UUID
    ) -> TransactionImport | None:
        lock_digest = sha256(
            f"{self.tenant_id}:{self.organization_id}:{self.legal_entity_id}:"
            f"{bank_account_id}:{source_sha256}".encode()
        ).digest()
        lock_key = int.from_bytes(lock_digest[:8], byteorder="big", signed=True)
        await self.session.execute(select(func.pg_advisory_xact_lock(lock_key)))
        return await self.session.scalar(
            select(TransactionImport).where(
                TransactionImport.tenant_id == self.tenant_id,
                TransactionImport.organization_id == self.organization_id,
                TransactionImport.legal_entity_id == self.legal_entity_id,
                TransactionImport.bank_account_id == bank_account_id,
                TransactionImport.source_sha256 == source_sha256,
            )
        )

    async def import_errors(self, import_id: UUID, *, limit: int) -> list[TransactionImportError]:
        return list(
            await self.session.scalars(
                select(TransactionImportError)
                .where(
                    TransactionImportError.tenant_id == self.tenant_id,
                    TransactionImportError.import_id == import_id,
                )
                .order_by(TransactionImportError.source_row_number)
                .limit(limit)
            )
        )

    async def list_transactions(
        self, *, limit: int, after: UUID | None, import_id: UUID | None = None
    ) -> list[BankTransaction]:
        query = select(BankTransaction).where(
            BankTransaction.tenant_id == self.tenant_id,
            BankTransaction.organization_id == self.organization_id,
            BankTransaction.legal_entity_id == self.legal_entity_id,
        )
        if import_id:
            query = query.where(BankTransaction.import_id == import_id)
        if after:
            query = query.where(BankTransaction.id > after)
        return list(await self.session.scalars(query.order_by(BankTransaction.id).limit(limit + 1)))

    async def get_transaction(self, transaction_id: UUID) -> BankTransaction | None:
        return await self.session.scalar(
            select(BankTransaction).where(
                BankTransaction.tenant_id == self.tenant_id,
                BankTransaction.organization_id == self.organization_id,
                BankTransaction.legal_entity_id == self.legal_entity_id,
                BankTransaction.id == transaction_id,
            )
        )

    async def get_job(self, job_id: UUID) -> ProcessingJob | None:
        return await self.session.scalar(
            select(ProcessingJob).where(
                ProcessingJob.tenant_id == self.tenant_id,
                ProcessingJob.organization_id == self.organization_id,
                ProcessingJob.legal_entity_id == self.legal_entity_id,
                ProcessingJob.id == job_id,
            )
        )

    def add_outbox(
        self,
        *,
        event_type: str,
        resource_type: str,
        resource_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> OutboxEvent:
        if event_type not in EVENT_REGISTRY:
            raise ValueError("event type is not registered in the Phase 0 contract")
        payload_reference = ResourceReference(
            resource_type=resource_type, resource_id=resource_id
        ).model_dump(mode="json")
        row = OutboxEvent(
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            event_id=uuid4(),
            event_type=event_type,
            schema_version="1.0",
            producer="ledgerai-backend",
            payload_reference=payload_reference,
            correlation_id=correlation_id,
            causation_id=causation_id,
            status=DeliveryStatus.PENDING,
        )
        self.session.add(row)
        return row

    def store_import_rows(
        self, import_row: TransactionImport, parsed: CsvParseResult
    ) -> list[BankTransaction]:
        transactions: list[BankTransaction] = []
        for item in parsed.rows:
            transaction = self._transaction(import_row, item)
            self.session.add(transaction)
            transactions.append(transaction)
        for error in parsed.errors:
            self.session.add(
                TransactionImportError(
                    tenant_id=self.tenant_id,
                    organization_id=self.organization_id,
                    legal_entity_id=self.legal_entity_id,
                    import_id=import_row.id,
                    source_row_number=error.source_row_number,
                    error_code=error.error_code,
                    safe_message=error.safe_message,
                )
            )
        import_row.accepted_count = len(transactions)
        import_row.rejected_count = len(parsed.errors)
        import_row.status = (
            ImportStatus.PARTIAL
            if transactions and parsed.errors
            else ImportStatus.COMPLETED
            if transactions
            else ImportStatus.FAILED
        )
        return transactions

    def _transaction(
        self, import_row: TransactionImport, item: ParsedTransaction
    ) -> BankTransaction:
        return BankTransaction(
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            import_id=import_row.id,
            bank_account_id=import_row.bank_account_id,
            source_row_number=item.source_row_number,
            booking_date=item.booking_date,
            value_date=item.value_date,
            amount=item.amount,
            currency=item.currency,
            direction=item.direction,
            narration=item.narration,
            reference=item.reference,
            counterparty_name=item.counterparty_name,
            counterparty_account=item.counterparty_account,
            external_source_id=item.external_source_id,
            source_fingerprint=item.source_fingerprint,
        )
