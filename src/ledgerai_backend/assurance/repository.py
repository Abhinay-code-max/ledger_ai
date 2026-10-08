"""Tenant-scoped persistence operations for Phase 4 assurance workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ledgerai_backend.assurance.models import (
    AccountingPeriod,
    AuditEvent,
    CloseRun,
    FinancialStatementLine,
    FinancialStatementSnapshot,
    PostingConfirmation,
    PostingOperation,
    ProgressEvent,
    ProgressProjection,
    ProvenanceEdge,
)
from ledgerai_backend.integration.models import ApprovalRequest, ApprovalStatus, JournalProposal


class AssuranceRepository:
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

    def scope_values(self) -> dict[str, UUID]:
        return {
            "tenant_id": self.tenant_id,
            "organization_id": self.organization_id,
            "legal_entity_id": self.legal_entity_id,
        }

    def _scope(self, model: type[Any]) -> tuple[Any, ...]:
        return (
            model.tenant_id == self.tenant_id,
            model.organization_id == self.organization_id,
            model.legal_entity_id == self.legal_entity_id,
        )

    async def lock_key(self, namespace: str, value: str) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"),
            {"value": f"{self.tenant_id}:{namespace}:{value}"},
        )

    async def eligible_journal(self, proposal_id: UUID, version: int) -> JournalProposal | None:
        approved = select(ApprovalRequest.id).where(
            *self._scope(ApprovalRequest),
            ApprovalRequest.subject_type == "journal_proposal",
            ApprovalRequest.subject_id == proposal_id,
            ApprovalRequest.subject_version == str(version),
            ApprovalRequest.status == ApprovalStatus.APPROVED,
        )
        return await self.session.scalar(
            select(JournalProposal).where(
                *self._scope(JournalProposal),
                JournalProposal.id == proposal_id,
                JournalProposal.proposal_version == version,
                JournalProposal.accounting_validation == "NOT_VALIDATED",
                JournalProposal.posting_status == "UNPOSTED",
                approved.exists(),
            )
        )

    async def period(self, period_id: UUID, *, lock: bool = False) -> AccountingPeriod | None:
        query = select(AccountingPeriod).where(
            *self._scope(AccountingPeriod), AccountingPeriod.id == period_id
        )
        if lock:
            return cast(AccountingPeriod | None, await self.session.scalar(query.with_for_update()))
        return cast(AccountingPeriod | None, await self.session.scalar(query))

    async def list_periods(self, *, limit: int = 100) -> list[AccountingPeriod]:
        return list(
            await self.session.scalars(
                select(AccountingPeriod)
                .where(*self._scope(AccountingPeriod))
                .order_by(AccountingPeriod.period_start.desc(), AccountingPeriod.id)
                .limit(limit)
            )
        )

    async def posting_by_idempotency(self, key: str) -> PostingOperation | None:
        return await self.session.scalar(
            select(PostingOperation).where(
                *self._scope(PostingOperation), PostingOperation.idempotency_key == key
            )
        )

    async def posting(self, operation_id: UUID, *, lock: bool = False) -> PostingOperation | None:
        query = select(PostingOperation).where(
            *self._scope(PostingOperation), PostingOperation.operation_id == operation_id
        )
        if lock:
            return cast(PostingOperation | None, await self.session.scalar(query.with_for_update()))
        return cast(PostingOperation | None, await self.session.scalar(query))

    async def confirmation(self, operation_id: UUID) -> PostingConfirmation | None:
        return await self.session.scalar(
            select(PostingConfirmation)
            .join(
                PostingOperation,
                and_(
                    PostingConfirmation.tenant_id == PostingOperation.tenant_id,
                    PostingConfirmation.posting_operation_id == PostingOperation.id,
                ),
            )
            .where(*self._scope(PostingConfirmation), PostingOperation.operation_id == operation_id)
        )

    async def close_by_idempotency(self, key: str) -> CloseRun | None:
        return await self.session.scalar(
            select(CloseRun).where(*self._scope(CloseRun), CloseRun.idempotency_key == key)
        )

    async def close_run(self, operation_id: UUID, *, lock: bool = False) -> CloseRun | None:
        query = select(CloseRun).where(
            *self._scope(CloseRun), CloseRun.operation_id == operation_id
        )
        if lock:
            return cast(CloseRun | None, await self.session.scalar(query.with_for_update()))
        return cast(CloseRun | None, await self.session.scalar(query))

    async def latest_audit_hash(self) -> str | None:
        # Serialize the per-tenant hash chain, including the first insert.
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:tenant, 0))"),
            {"tenant": str(self.tenant_id)},
        )
        return await self.session.scalar(
            select(AuditEvent.event_hash)
            .where(*self._scope(AuditEvent))
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .limit(1)
        )

    async def list_audit(
        self,
        *,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        filters: list[Any] = [*self._scope(AuditEvent)]
        if resource_type is not None:
            filters.append(AuditEvent.resource_type == resource_type)
        if resource_id is not None:
            filters.append(AuditEvent.resource_id == resource_id)
        return list(
            await self.session.scalars(
                select(AuditEvent)
                .where(*filters)
                .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
                .limit(limit)
            )
        )

    async def edges_for(self, resource_type: str, resource_id: UUID) -> list[ProvenanceEdge]:
        return list(
            await self.session.scalars(
                select(ProvenanceEdge).where(
                    *self._scope(ProvenanceEdge),
                    or_(
                        and_(
                            ProvenanceEdge.from_type == resource_type,
                            ProvenanceEdge.from_id == resource_id,
                        ),
                        and_(
                            ProvenanceEdge.to_type == resource_type,
                            ProvenanceEdge.to_id == resource_id,
                        ),
                    ),
                )
            )
        )

    async def projection(
        self, resource_type: str, resource_id: UUID, *, lock: bool = False
    ) -> ProgressProjection | None:
        query = select(ProgressProjection).where(
            *self._scope(ProgressProjection),
            ProgressProjection.resource_type == resource_type,
            ProgressProjection.resource_id == resource_id,
        )
        if lock:
            return cast(
                ProgressProjection | None, await self.session.scalar(query.with_for_update())
            )
        return cast(ProgressProjection | None, await self.session.scalar(query))

    async def progress_after(
        self, last_event_id: UUID | None, *, limit: int = 100
    ) -> list[ProgressEvent]:
        query = select(ProgressEvent).where(*self._scope(ProgressEvent))
        if last_event_id is not None:
            cursor = await self.session.scalar(
                select(ProgressEvent).where(
                    *self._scope(ProgressEvent),
                    ProgressEvent.progress_event_id == last_event_id,
                )
            )
            if cursor is None:
                return []
            query = query.where(
                or_(
                    ProgressEvent.occurred_at > cursor.occurred_at,
                    and_(
                        ProgressEvent.occurred_at == cursor.occurred_at,
                        ProgressEvent.id > cursor.id,
                    ),
                )
            )
        return list(
            await self.session.scalars(
                query.order_by(ProgressEvent.occurred_at, ProgressEvent.id).limit(limit)
            )
        )

    async def has_progress_event(self, event_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(ProgressEvent.id).where(
                    *self._scope(ProgressEvent), ProgressEvent.progress_event_id == event_id
                )
            )
            is not None
        )

    async def statement(self, snapshot_id: UUID) -> FinancialStatementSnapshot | None:
        return await self.session.scalar(
            select(FinancialStatementSnapshot).where(
                *self._scope(FinancialStatementSnapshot),
                FinancialStatementSnapshot.id == snapshot_id,
            )
        )

    async def statement_by_role2_id(self, snapshot_id: UUID) -> FinancialStatementSnapshot | None:
        return await self.session.scalar(
            select(FinancialStatementSnapshot).where(
                *self._scope(FinancialStatementSnapshot),
                FinancialStatementSnapshot.role2_snapshot_id == snapshot_id,
            )
        )

    async def statement_lines(self, snapshot_id: UUID) -> list[FinancialStatementLine]:
        return list(
            await self.session.scalars(
                select(FinancialStatementLine)
                .where(
                    *self._scope(FinancialStatementLine),
                    FinancialStatementLine.snapshot_id == snapshot_id,
                )
                .order_by(FinancialStatementLine.line_key)
            )
        )

    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)
