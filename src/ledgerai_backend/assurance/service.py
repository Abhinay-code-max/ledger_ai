"""Idempotent Phase 4 orchestration with immutable accounting evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from ledgerai_backend.assurance.models import (
    AccountingPeriod,
    AuditEvent,
    CloseRun,
    CloseState,
    FinancialStatementLine,
    PeriodState,
    PostingConfirmation,
    PostingOperation,
    PostingState,
    ProgressEvent,
    ProgressProjection,
    ProvenanceEdge,
)
from ledgerai_backend.assurance.models import (
    FinancialStatementSnapshot as StatementRow,
)
from ledgerai_backend.assurance.repository import AssuranceRepository
from ledgerai_backend.assurance.schemas import (
    AccountingPeriodCreate,
    PostingOperationCreate,
    ProvenanceEdgeResponse,
    ProvenanceNode,
    ProvenanceTraceResponse,
)
from ledgerai_backend.core.errors import ApiError
from ledgerai_backend.core.request_context import AuthorizationContext
from ledgerai_backend.integration.adapters import AdapterError
from ledgerai_contracts.v1.accounting import (
    AccountingValidationResult,
    FinancialStatementRequest,
    FinancialStatementSnapshot,
    JournalPostingRequest,
    JournalPostingResult,
    PeriodCloseRequest,
    PeriodCloseResult,
    PeriodCloseValidationResult,
    PostingStatusResult,
)
from ledgerai_contracts.v1.common import (
    CorrelationMetadata,
    ProducerMetadata,
    ProducerType,
    ResourceReference,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class Role2AssurancePort(Protocol):
    async def validate_posting(self, **kwargs: Any) -> AccountingValidationResult: ...

    async def post_journal(self, **kwargs: Any) -> JournalPostingResult: ...

    async def posting_status(self, **kwargs: Any) -> PostingStatusResult: ...

    async def validate_period_close(self, **kwargs: Any) -> PeriodCloseValidationResult: ...

    async def close_period(self, **kwargs: Any) -> PeriodCloseResult: ...

    async def period_close_status(self, **kwargs: Any) -> PeriodCloseResult: ...

    async def financial_statement(self, **kwargs: Any) -> FinancialStatementSnapshot: ...


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


class AssuranceService:
    def __init__(
        self,
        repository: AssuranceRepository,
        context: AuthorizationContext,
        role2: Role2AssurancePort | None,
    ) -> None:
        self.repository = repository
        self.context = context
        self.role2 = role2

    @property
    def tenant_context(self) -> EntityTenantContext:
        return EntityTenantContext(
            tenant_id=self.context.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
        )

    @property
    def correlation_id(self) -> UUID:
        return UUID(self.context.correlation_id)

    def _correlation(self, causation_id: UUID | None = None) -> CorrelationMetadata:
        return CorrelationMetadata(
            request_id=UUID(self.context.request_id),
            correlation_id=self.correlation_id,
            causation_id=causation_id,
        )

    @staticmethod
    def _producer() -> ProducerMetadata:
        return ProducerMetadata(
            producer_type=ProducerType.SERVICE, name="ledgerai-backend", version="1.3.0"
        )

    def _require_role2(self) -> Role2AssurancePort:
        if self.role2 is None:
            raise ApiError(
                503,
                "DOWNSTREAM",
                "ACCOUNTING_SERVICE_UNAVAILABLE",
                "The accounting service is unavailable.",
            )
        return self.role2

    async def create_period(self, body: AccountingPeriodCreate) -> AccountingPeriod:
        row = AccountingPeriod(
            **self.repository.scope_values(),
            period_start=body.period_start,
            period_end=body.period_end,
            currency=body.currency,
            state=PeriodState.OPEN,
        )
        self.repository.session.add(row)
        await self.repository.session.flush()
        await self.audit(
            action="ACCOUNTING_PERIOD_CREATED",
            resource_type="accounting_period",
            resource_id=row.id,
            resource_version=str(row.version),
            outcome="SUCCEEDED",
            metadata={"period_start": str(row.period_start), "period_end": str(row.period_end)},
        )
        await self.progress(
            resource_type="accounting_period",
            resource_id=row.id,
            resource_version=str(row.version),
            stage="PERIOD",
            status="OPEN",
            percent=0,
        )
        return row

    async def start_posting(
        self, body: PostingOperationCreate, *, idempotency_key: str
    ) -> PostingOperation:
        request_hash = _canonical_hash(body.model_dump(mode="json"))
        await self.repository.lock_key("posting", idempotency_key)
        duplicate = await self.repository.posting_by_idempotency(idempotency_key)
        if duplicate is not None:
            if duplicate.request_hash != request_hash:
                raise ApiError(
                    409,
                    "CONFLICT",
                    "IDEMPOTENCY_CONFLICT",
                    "Idempotency key conflicts with another posting request.",
                )
            return duplicate
        period = await self.repository.period(body.accounting_period_id, lock=True)
        proposal = await self.repository.eligible_journal(
            body.journal_proposal_id, body.proposal_version
        )
        if period is None or proposal is None:
            raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
        if period.state != PeriodState.OPEN:
            raise ApiError(409, "CONFLICT", "PERIOD_NOT_OPEN", "The accounting period is not open.")
        if not period.period_start <= proposal.proposed_journal_date <= period.period_end:
            raise ApiError(
                409,
                "CONFLICT",
                "POSTING_DATE_OUTSIDE_PERIOD",
                "The journal date is outside the selected accounting period.",
            )
        row = PostingOperation(
            **self.repository.scope_values(),
            journal_proposal_id=body.journal_proposal_id,
            proposal_version=body.proposal_version,
            accounting_period_id=period.id,
            state=PostingState.REQUESTED,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            requested_by_principal_id=self.context.principal_id,
            correlation_id=self.correlation_id,
        )
        self.repository.session.add(row)
        await self.repository.session.flush()
        await self._posting_progress(row, "REQUESTED", 5)
        await self.audit(
            action="JOURNAL_POSTING_REQUESTED",
            resource_type="posting_operation",
            resource_id=row.operation_id,
            resource_version=str(row.version),
            outcome="PENDING",
            metadata={"proposal_id": str(row.journal_proposal_id)},
        )
        await self._execute_posting(row)
        return row

    async def _execute_posting(self, row: PostingOperation) -> None:
        role2 = self._require_role2()
        assert row.accounting_period_id is not None
        request = JournalPostingRequest(
            schema_version="1.0",
            tenant_context=self.tenant_context,
            operation_id=row.operation_id,
            proposal=ResourceReference(
                resource_type="journal_proposal",
                resource_id=row.journal_proposal_id,
                resource_version=str(row.proposal_version),
            ),
            proposal_version=row.proposal_version,
            accounting_period_id=row.accounting_period_id,
            requested_at=datetime.now(UTC),
            producer=self._producer(),
            correlation=self._correlation(),
        )
        row.state = PostingState.VALIDATING
        row.version += 1
        await self._posting_progress(row, "VALIDATING", 20)
        kwargs = self._adapter_kwargs(row.operation_id, request.model_dump(mode="json"))
        try:
            validation = await role2.validate_posting(**kwargs)
            self._bind_posting_result(row, validation)
            if validation.outcome not in {"ACCEPTED", "VALIDATED"}:
                row.state = (
                    PostingState.REJECTED
                    if validation.outcome == "REJECTED"
                    else PostingState.FAILED
                )
                row.last_error_code = validation.issues[0].code if validation.issues else None
                row.version += 1
                await self._posting_progress(row, row.state.value, 100)
                return
            row.state = PostingState.IN_PROGRESS
            row.version += 1
            await self._posting_progress(row, "IN_PROGRESS", 50)
            result = await role2.post_journal(**kwargs)
            await self._apply_posting_result(row, result)
        except AdapterError as exc:
            await self._adapter_failure(row, exc)

    async def refresh_posting(self, operation_id: UUID) -> PostingOperation:
        row = await self.repository.posting(operation_id, lock=True)
        if row is None:
            raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
        if row.state not in {PostingState.UNKNOWN, PostingState.IN_PROGRESS}:
            return row
        role2 = self._require_role2()
        try:
            result = await role2.posting_status(
                **self._adapter_kwargs(row.operation_id, {"operation_id": str(row.operation_id)})
            )
            await self._apply_posting_result(row, result)
        except AdapterError as exc:
            await self._adapter_failure(row, exc)
        return row

    def _bind_posting_result(
        self, row: PostingOperation, result: AccountingValidationResult | JournalPostingResult
    ) -> None:
        if (
            result.operation_id != row.operation_id
            or result.proposal_id != row.journal_proposal_id
            or result.proposal_version != row.proposal_version
        ):
            raise AdapterError("WRONG_WORKFLOW_RESOURCE")

    async def _apply_posting_result(
        self, row: PostingOperation, result: JournalPostingResult
    ) -> None:
        self._bind_posting_result(row, result)
        state = {
            "POSTED": PostingState.CONFIRMED,
            "REJECTED": PostingState.REJECTED,
            "IN_PROGRESS": PostingState.IN_PROGRESS,
            "UNKNOWN": PostingState.UNKNOWN,
            "FAILED": PostingState.FAILED,
        }[result.outcome]
        row.state = state
        row.last_error_code = result.issues[0].code if result.issues else None
        row.version += 1
        if state == PostingState.CONFIRMED:
            assert result.posted_journal_id is not None and result.posted_at is not None
            self.repository.session.add(
                PostingConfirmation(
                    **self.repository.scope_values(),
                    posting_operation_id=row.id,
                    posted_journal_id=result.posted_journal_id,
                    role2_version=result.producer.version,
                    ledger_references=[
                        item.model_dump(mode="json") for item in result.ledger_references
                    ],
                    confirmed_at=result.posted_at,
                )
            )
            for reference in result.ledger_references:
                self.repository.session.add(
                    ProvenanceEdge(
                        **self.repository.scope_values(),
                        from_type="journal_proposal",
                        from_id=row.journal_proposal_id,
                        from_version=str(row.proposal_version),
                        to_type=reference.resource_type,
                        to_id=reference.resource_id,
                        to_version=reference.resource_version or "",
                        relation="POSTED_AS",
                    )
                )
        await self._posting_progress(
            row, state.value, 100 if state != PostingState.IN_PROGRESS else 75
        )
        await self.audit(
            action="JOURNAL_POSTING_RESULT",
            resource_type="posting_operation",
            resource_id=row.operation_id,
            resource_version=str(row.version),
            outcome="SUCCEEDED" if state == PostingState.CONFIRMED else "PENDING",
            metadata={"state": state.value},
        )

    async def _adapter_failure(self, row: PostingOperation, exc: AdapterError) -> None:
        row.state = PostingState.UNKNOWN if exc.unknown_outcome else PostingState.FAILED
        row.last_error_code = exc.code
        row.version += 1
        await self._posting_progress(row, row.state.value, None, exc.code)
        await self.audit(
            action="JOURNAL_POSTING_RESULT",
            resource_type="posting_operation",
            resource_id=row.operation_id,
            resource_version=str(row.version),
            outcome="PENDING" if exc.unknown_outcome else "FAILED",
            metadata={"error_code": exc.code},
        )

    async def start_close(self, period_id: UUID, *, idempotency_key: str) -> CloseRun:
        request_hash = _canonical_hash({"period_id": str(period_id)})
        await self.repository.lock_key("period-close", idempotency_key)
        duplicate = await self.repository.close_by_idempotency(idempotency_key)
        if duplicate is not None:
            if duplicate.request_hash != request_hash:
                raise ApiError(
                    409,
                    "CONFLICT",
                    "IDEMPOTENCY_CONFLICT",
                    "Idempotency key conflicts with another close request.",
                )
            return duplicate
        period = await self.repository.period(period_id, lock=True)
        if period is None:
            raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
        if period.state not in {PeriodState.OPEN, PeriodState.BLOCKED, PeriodState.FAILED}:
            raise ApiError(
                409, "CONFLICT", "PERIOD_NOT_CLOSEABLE", "The period cannot be closed now."
            )
        row = CloseRun(
            **self.repository.scope_values(),
            accounting_period_id=period.id,
            state=CloseState.REQUESTED,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            requested_by_principal_id=self.context.principal_id,
            correlation_id=self.correlation_id,
        )
        self.repository.session.add(row)
        period.state = PeriodState.CLOSE_REQUESTED
        period.version += 1
        await self.repository.session.flush()
        await self.progress(
            resource_type="accounting_period",
            resource_id=period.id,
            resource_version=str(period.version),
            stage="PERIOD_CLOSE",
            status="REQUESTED",
            percent=5,
        )
        await self.audit(
            action="PERIOD_CLOSE_REQUESTED",
            resource_type="accounting_period",
            resource_id=period.id,
            resource_version=str(period.version),
            outcome="PENDING",
            metadata={"operation_id": str(row.operation_id)},
        )
        await self._execute_close(row, period)
        return row

    async def _execute_close(self, row: CloseRun, period: AccountingPeriod) -> None:
        role2 = self._require_role2()
        request = PeriodCloseRequest(
            schema_version="1.0",
            tenant_context=self.tenant_context,
            operation_id=row.operation_id,
            accounting_period_id=period.id,
            period_start=period.period_start,
            period_end=period.period_end,
            requested_at=datetime.now(UTC),
            producer=self._producer(),
            correlation=self._correlation(),
        )
        kwargs = self._adapter_kwargs(row.operation_id, request.model_dump(mode="json"))
        row.state, period.state = CloseState.VALIDATING, PeriodState.VALIDATING
        row.version += 1
        period.version += 1
        await self.progress(
            resource_type="accounting_period",
            resource_id=period.id,
            resource_version=str(period.version),
            stage="PERIOD_CLOSE",
            status="VALIDATING",
            percent=20,
        )
        try:
            validation = await role2.validate_period_close(**kwargs)
            self._bind_close_result(row, validation)
            if validation.outcome != "VALIDATED":
                row.state = (
                    CloseState.BLOCKED
                    if validation.outcome in {"BLOCKED", "REJECTED"}
                    else CloseState.FAILED
                )
                period.state = (
                    PeriodState.BLOCKED if row.state == CloseState.BLOCKED else PeriodState.FAILED
                )
                row.last_error_code = validation.issues[0].code if validation.issues else None
                row.version += 1
                period.version += 1
                await self.progress(
                    resource_type="accounting_period",
                    resource_id=period.id,
                    resource_version=str(period.version),
                    stage="PERIOD_CLOSE",
                    status=row.state.value,
                    percent=100,
                    reason_code=row.last_error_code,
                )
                await self.audit(
                    action="PERIOD_CLOSE_RESULT",
                    resource_type="accounting_period",
                    resource_id=period.id,
                    resource_version=str(period.version),
                    outcome="FAILED",
                    metadata={"state": row.state.value},
                )
                return
            row.state, period.state = CloseState.IN_PROGRESS, PeriodState.CLOSING
            row.version += 1
            period.version += 1
            result = await role2.close_period(**kwargs)
            await self._apply_close_result(row, period, result)
        except AdapterError as exc:
            row.state = CloseState.UNKNOWN if exc.unknown_outcome else CloseState.FAILED
            period.state = PeriodState.CLOSING if exc.unknown_outcome else PeriodState.FAILED
            row.last_error_code = exc.code
            row.version += 1
            period.version += 1
            await self.progress(
                resource_type="accounting_period",
                resource_id=period.id,
                resource_version=str(period.version),
                stage="PERIOD_CLOSE",
                status=row.state.value,
                percent=None,
                reason_code=exc.code,
            )
            await self.audit(
                action="PERIOD_CLOSE_RESULT",
                resource_type="accounting_period",
                resource_id=period.id,
                resource_version=str(period.version),
                outcome="PENDING" if exc.unknown_outcome else "FAILED",
                metadata={"error_code": exc.code},
            )

    async def refresh_close(self, operation_id: UUID) -> CloseRun:
        row = await self.repository.close_run(operation_id, lock=True)
        if row is None:
            raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
        period = await self.repository.period(row.accounting_period_id, lock=True)
        if period is None:
            raise ApiError(
                409, "CONFLICT", "PERIOD_MISSING", "The accounting period is unavailable."
            )
        if row.state not in {CloseState.UNKNOWN, CloseState.IN_PROGRESS}:
            return row
        try:
            result = await self._require_role2().period_close_status(
                **self._adapter_kwargs(row.operation_id, {"operation_id": str(row.operation_id)})
            )
            await self._apply_close_result(row, period, result)
        except AdapterError as exc:
            row.state = CloseState.UNKNOWN if exc.unknown_outcome else CloseState.FAILED
            period.state = PeriodState.CLOSING if exc.unknown_outcome else PeriodState.FAILED
            row.last_error_code = exc.code
            row.version += 1
            period.version += 1
            await self.progress(
                resource_type="accounting_period",
                resource_id=period.id,
                resource_version=str(period.version),
                stage="PERIOD_CLOSE",
                status=row.state.value,
                percent=None,
                reason_code=exc.code,
            )
            await self.audit(
                action="PERIOD_CLOSE_RECOVERY_RESULT",
                resource_type="accounting_period",
                resource_id=period.id,
                resource_version=str(period.version),
                outcome="PENDING" if exc.unknown_outcome else "FAILED",
                metadata={"error_code": exc.code},
            )
        return row

    @staticmethod
    def _bind_close_result(
        row: CloseRun, result: PeriodCloseValidationResult | PeriodCloseResult
    ) -> None:
        if (
            result.operation_id != row.operation_id
            or result.accounting_period_id != row.accounting_period_id
        ):
            raise AdapterError("WRONG_WORKFLOW_RESOURCE")

    async def _apply_close_result(
        self, row: CloseRun, period: AccountingPeriod, result: PeriodCloseResult
    ) -> None:
        self._bind_close_result(row, result)
        row.role2_version = result.producer.version
        row.last_error_code = result.issues[0].code if result.issues else None
        row.state = {
            "CLOSED": CloseState.CONFIRMED,
            "BLOCKED": CloseState.BLOCKED,
            "REJECTED": CloseState.BLOCKED,
            "IN_PROGRESS": CloseState.IN_PROGRESS,
            "UNKNOWN": CloseState.UNKNOWN,
            "FAILED": CloseState.FAILED,
        }[result.outcome]
        period.state = {
            CloseState.CONFIRMED: PeriodState.CLOSED,
            CloseState.BLOCKED: PeriodState.BLOCKED,
            CloseState.IN_PROGRESS: PeriodState.CLOSING,
            CloseState.UNKNOWN: PeriodState.CLOSING,
            CloseState.FAILED: PeriodState.FAILED,
        }[row.state]
        if row.state == CloseState.CONFIRMED:
            period.closed_at = result.closed_at
        row.version += 1
        period.version += 1
        await self.progress(
            resource_type="accounting_period",
            resource_id=period.id,
            resource_version=str(period.version),
            stage="PERIOD_CLOSE",
            status=row.state.value,
            percent=100 if row.state != CloseState.IN_PROGRESS else 75,
            reason_code=row.last_error_code,
        )
        await self.audit(
            action="PERIOD_CLOSE_RESULT",
            resource_type="accounting_period",
            resource_id=period.id,
            resource_version=str(period.version),
            outcome="SUCCEEDED" if row.state == CloseState.CONFIRMED else "PENDING",
            metadata={"state": row.state.value},
        )

    async def request_statement(self, period_id: UUID, statement_type: str) -> StatementRow:
        period = await self.repository.period(period_id)
        if period is None:
            raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
        operation_id = uuid4()
        request = FinancialStatementRequest(
            schema_version="1.0",
            tenant_context=self.tenant_context,
            operation_id=operation_id,
            accounting_period_id=period.id,
            statement_type=statement_type,  # type: ignore[arg-type]
            as_of=datetime.now(UTC),
            correlation=self._correlation(),
        )
        result = await self._require_role2().financial_statement(
            **self._adapter_kwargs(operation_id, request.model_dump(mode="json"))
        )
        if result.accounting_period_id != period.id or result.status != "AVAILABLE":
            raise ApiError(
                503,
                "DOWNSTREAM",
                "STATEMENT_NOT_AVAILABLE",
                "The financial statement is not available.",
            )
        duplicate = await self.repository.statement_by_role2_id(result.snapshot_id)
        if duplicate is not None:
            return duplicate
        row = StatementRow(
            **self.repository.scope_values(),
            accounting_period_id=period.id,
            role2_snapshot_id=result.snapshot_id,
            statement_type=result.statement_type,
            currency=result.currency,
            as_of=result.as_of,
            role2_version=result.producer.version,
            correlation_id=self.correlation_id,
        )
        self.repository.session.add(row)
        await self.repository.session.flush()
        for line in result.lines:
            self.repository.session.add(
                FinancialStatementLine(
                    **self.repository.scope_values(),
                    snapshot_id=row.id,
                    line_key=line.line_id,
                    account_reference=line.account_reference,
                    label=line.label,
                    amount=line.amount.amount,
                    currency=line.amount.currency,
                    ledger_references=[
                        reference.model_dump(mode="json") for reference in line.ledger_references
                    ],
                )
            )
        await self.audit(
            action="FINANCIAL_STATEMENT_CAPTURED",
            resource_type="financial_statement_snapshot",
            resource_id=row.id,
            resource_version=str(result.snapshot_id),
            outcome="SUCCEEDED",
            metadata={"statement_type": result.statement_type},
        )
        return row

    async def trace(
        self, resource_type: str, resource_id: UUID, *, maximum_nodes: int = 500
    ) -> ProvenanceTraceResponse:
        root = ProvenanceNode(resource_type=resource_type, resource_id=resource_id)
        nodes: dict[tuple[str, UUID, str | None], ProvenanceNode] = {
            (resource_type, resource_id, None): root
        }
        edges: dict[UUID, ProvenanceEdgeResponse] = {}
        queue = [(resource_type, resource_id)]
        visited: set[tuple[str, UUID]] = set()
        truncated = False
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edge in await self.repository.edges_for(*current):
                source = ProvenanceNode(
                    resource_type=edge.from_type,
                    resource_id=edge.from_id,
                    resource_version=edge.from_version or None,
                )
                target = ProvenanceNode(
                    resource_type=edge.to_type,
                    resource_id=edge.to_id,
                    resource_version=edge.to_version or None,
                )
                nodes[(source.resource_type, source.resource_id, source.resource_version)] = source
                nodes[(target.resource_type, target.resource_id, target.resource_version)] = target
                edges[edge.id] = ProvenanceEdgeResponse(
                    source=source, target=target, relation=edge.relation
                )
                for node in (source, target):
                    key = (node.resource_type, node.resource_id)
                    if key not in visited:
                        queue.append(key)
                if len(nodes) >= maximum_nodes:
                    truncated = bool(queue)
                    queue.clear()
                    break
        return ProvenanceTraceResponse(
            root=root, nodes=list(nodes.values()), edges=list(edges.values()), truncated=truncated
        )

    async def audit(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: UUID,
        resource_version: str | None,
        outcome: str,
        metadata: dict[str, object],
        causation_id: UUID | None = None,
    ) -> AuditEvent:
        previous_hash = await self.repository.latest_audit_hash()
        # The repository holds a tenant-scoped transaction advisory lock here,
        # so this timestamp preserves the same order as the hash chain.
        occurred_at = datetime.now(UTC)
        event_id = uuid4()
        material = {
            "audit_event_id": str(event_id),
            "tenant_id": str(self.context.tenant_id),
            "actor_id": str(self.context.principal_id),
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "resource_version": resource_version,
            "outcome": outcome,
            "correlation_id": str(self.correlation_id),
            "causation_id": str(causation_id) if causation_id else None,
            "metadata": metadata,
            "occurred_at": occurred_at.isoformat(),
            "previous_hash": previous_hash,
        }
        row = AuditEvent(
            **self.repository.scope_values(),
            audit_event_id=event_id,
            actor_type="HUMAN",
            actor_id=str(self.context.principal_id),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_version=resource_version,
            outcome=outcome,
            correlation_id=self.correlation_id,
            causation_id=causation_id,
            audit_metadata=metadata,
            previous_hash=previous_hash,
            event_hash=_canonical_hash(material),
            occurred_at=occurred_at,
        )
        self.repository.session.add(row)
        await self.repository.session.flush()
        return row

    async def progress(
        self,
        *,
        resource_type: str,
        resource_id: UUID,
        resource_version: str,
        stage: str,
        status: str,
        percent: int | None,
        reason_code: str | None = None,
    ) -> ProgressEvent:
        await self.repository.lock_key("progress", f"{resource_type}:{resource_id}")
        occurred_at = datetime.now(UTC)
        row = ProgressEvent(
            **self.repository.scope_values(),
            resource_type=resource_type,
            resource_id=resource_id,
            resource_version=resource_version,
            stage=stage,
            status=status,
            correlation_id=self.correlation_id,
            percent=percent,
            reason_code=reason_code,
            occurred_at=occurred_at,
        )
        self.repository.session.add(row)
        await self.repository.session.flush()
        projection = await self.repository.projection(resource_type, resource_id, lock=True)
        if projection is None:
            projection = ProgressProjection(
                **self.repository.scope_values(),
                resource_type=resource_type,
                resource_id=resource_id,
                resource_version=resource_version,
                stage=stage,
                status=status,
                last_event_id=row.progress_event_id,
                correlation_id=self.correlation_id,
                percent=percent,
                reason_code=reason_code,
                occurred_at=occurred_at,
            )
            self.repository.session.add(projection)
        else:
            projection.resource_version = resource_version
            projection.stage = stage
            projection.status = status
            projection.last_event_id = row.progress_event_id
            projection.correlation_id = self.correlation_id
            projection.percent = percent
            projection.reason_code = reason_code
            projection.occurred_at = occurred_at
            projection.version += 1
        return row

    async def _posting_progress(
        self,
        row: PostingOperation,
        status: str,
        percent: int | None,
        reason_code: str | None = None,
    ) -> None:
        await self.progress(
            resource_type="posting_operation",
            resource_id=row.operation_id,
            resource_version=str(row.version),
            stage="JOURNAL_POSTING",
            status=status,
            percent=percent,
            reason_code=reason_code,
        )

    def _adapter_kwargs(self, operation_id: UUID, payload: dict[str, object]) -> dict[str, object]:
        return {
            "payload": payload,
            "tenant_context": self.tenant_context,
            "operation_id": operation_id,
            "correlation_id": self.correlation_id,
        }
