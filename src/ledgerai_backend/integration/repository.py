"""Tenant-explicit Phase 3 persistence operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ledgerai_backend.assurance.models import AuditEvent, ProvenanceEdge
from ledgerai_backend.assurance.service import add_provenance_edge, record_audit_event
from ledgerai_backend.ingestion.models import DocumentStatus, DocumentVersion
from ledgerai_backend.ingestion.repository import IngestionRepository
from ledgerai_backend.integration.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStatus,
    DocumentExtraction,
    ExceptionResolution,
    ExceptionSeverity,
    JournalProposal,
    MatchProposal,
    PolicyDecision,
    PolicyRule,
    PolicySet,
    WorkflowException,
)


class IntegrationRepository:
    def __init__(
        self, session: AsyncSession, tenant_id: UUID, organization_id: UUID, legal_entity_id: UUID
    ) -> None:
        self.session = session
        self.tenant_id, self.organization_id, self.legal_entity_id = (
            tenant_id,
            organization_id,
            legal_entity_id,
        )

    def _scope(self, model: type[Any]) -> tuple[Any, ...]:
        return (
            model.tenant_id == self.tenant_id,
            model.organization_id == self.organization_id,
            model.legal_entity_id == self.legal_entity_id,
        )

    async def list_rows(
        self,
        model: type[Any],
        *,
        limit: int,
        after: UUID | None,
        filters: tuple[Any, ...] = (),
    ) -> list[Any]:
        query = select(model).where(*self._scope(model), *filters)
        if after:
            query = query.where(model.id > after)
        return list(await self.session.scalars(query.order_by(model.id).limit(limit + 1)))

    async def get(self, model: type[Any], resource_id: UUID) -> Any | None:
        return await self.session.scalar(
            select(model).where(*self._scope(model), model.id == resource_id)
        )

    async def lock_approval(self, request_id: UUID) -> ApprovalRequest | None:
        return await self.session.scalar(
            select(ApprovalRequest)
            .where(*self._scope(ApprovalRequest), ApprovalRequest.id == request_id)
            .with_for_update()
        )

    async def existing_action(
        self, *, actor_id: UUID, idempotency_key: str
    ) -> ApprovalAction | None:
        return await self.session.scalar(
            select(ApprovalAction).where(
                ApprovalAction.tenant_id == self.tenant_id,
                ApprovalAction.actor_principal_id == actor_id,
                ApprovalAction.idempotency_key == idempotency_key,
            )
        )

    async def policy_decision(self, decision_id: UUID) -> PolicyDecision | None:
        return await self.session.scalar(
            select(PolicyDecision).where(
                *self._scope(PolicyDecision), PolicyDecision.id == decision_id
            )
        )

    async def policy_rules(self, policy_set_id: UUID) -> list[PolicyRule]:
        return list(
            await self.session.scalars(
                select(PolicyRule)
                .where(
                    *self._scope(PolicyRule),
                    PolicyRule.policy_set_id == policy_set_id,
                )
                .order_by(PolicyRule.priority.desc(), PolicyRule.rule_id)
            )
        )

    async def journal(self, proposal_id: UUID) -> JournalProposal | None:
        return await self.session.scalar(
            select(JournalProposal).where(
                *self._scope(JournalProposal), JournalProposal.id == proposal_id
            )
        )

    async def has_newer_journal_version(self, proposal: JournalProposal) -> bool:
        newer = await self.session.scalar(
            select(JournalProposal.id)
            .where(
                *self._scope(JournalProposal),
                JournalProposal.proposal_series_id == proposal.proposal_series_id,
                JournalProposal.proposal_version > proposal.proposal_version,
            )
            .limit(1)
        )
        return newer is not None

    async def has_blocking_exception(self) -> bool:
        row = await self.session.scalar(
            select(WorkflowException.id)
            .where(
                *self._scope(WorkflowException),
                WorkflowException.resolution_status.in_(
                    [ExceptionResolution.OPEN, ExceptionResolution.IN_REVIEW]
                ),
                WorkflowException.severity.in_(
                    [ExceptionSeverity.HIGH, ExceptionSeverity.CRITICAL]
                ),
            )
            .limit(1)
        )
        return row is not None

    def add_outbox(self, **kwargs: object) -> None:
        IngestionRepository(
            self.session, self.tenant_id, self.organization_id, self.legal_entity_id
        ).add_outbox(**kwargs)  # type: ignore[arg-type]

    @staticmethod
    def terminal(status: ApprovalStatus) -> bool:
        return status not in {ApprovalStatus.OPEN}

    @staticmethod
    def expired(row: ApprovalRequest) -> bool:
        return row.expires_at <= datetime.now(UTC)

    async def record_audit(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: UUID,
        resource_version: str | None = "1",
        outcome: str = "SUCCEEDED",
        metadata: dict[str, object] | None = None,
        actor_id: str = "system",
        actor_type: str = "HUMAN",
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        occurred_at: datetime | None = None,
    ) -> AuditEvent:
        return await record_audit_event(
            self.session,
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_version=resource_version,
            outcome=outcome,
            metadata=metadata,
            actor_id=actor_id,
            actor_type=actor_type,
            correlation_id=correlation_id,
            causation_id=causation_id,
            occurred_at=occurred_at,
        )

    async def add_edge(
        self,
        *,
        from_type: str,
        from_id: UUID,
        from_version: str = "1",
        to_type: str,
        to_id: UUID,
        to_version: str = "1",
        relation: str,
    ) -> ProvenanceEdge:
        return await add_provenance_edge(
            self.session,
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            from_type=from_type,
            from_id=from_id,
            from_version=from_version,
            to_type=to_type,
            to_id=to_id,
            to_version=to_version,
            relation=relation,
        )

    async def get_accepted_document_version(
        self, document_id: UUID, *, version_id: UUID | None = None
    ) -> DocumentVersion | None:
        query = select(DocumentVersion).where(
            *self._scope(DocumentVersion),
            DocumentVersion.document_id == document_id,
            DocumentVersion.status == DocumentStatus.ACCEPTED,
        )
        if version_id is not None:
            query = query.where(DocumentVersion.id == version_id)
        return await self.session.scalar(query.order_by(DocumentVersion.version_number.desc()))

    async def latest_extraction_for_version(
        self, document_version_id: UUID
    ) -> DocumentExtraction | None:
        return await self.session.scalar(
            select(DocumentExtraction)
            .where(
                *self._scope(DocumentExtraction),
                DocumentExtraction.document_version_id == document_version_id,
            )
            .order_by(DocumentExtraction.extraction_version.desc())
        )

    async def latest_match_proposal(self) -> MatchProposal | None:
        return await self.session.scalar(
            select(MatchProposal)
            .where(*self._scope(MatchProposal))
            .order_by(MatchProposal.id.desc())
            .limit(1)
        )

    async def get_policy_set_by_code(self, code: str) -> PolicySet | None:
        return await self.session.scalar(
            select(PolicySet).where(*self._scope(PolicySet), PolicySet.code == code)
        )
