"""Tenant-explicit Phase 3 persistence operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ledgerai_backend.ingestion.repository import IngestionRepository
from ledgerai_backend.integration.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStatus,
    ExceptionResolution,
    ExceptionSeverity,
    JournalProposal,
    PolicyDecision,
    PolicyRule,
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
