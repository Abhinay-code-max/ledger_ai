from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
import pytest

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
    ProvenanceEdge,
)
from ledgerai_backend.assurance.models import (
    FinancialStatementSnapshot as StatementRow,
)
from ledgerai_backend.assurance.repository import AssuranceRepository
from ledgerai_backend.assurance.service import AssuranceService, Role2AssurancePort
from ledgerai_backend.core.request_context import AuthorizationContext
from ledgerai_backend.integration.adapters import (
    AdapterSecurity,
    Role2Adapter,
    SignedServiceTokenProvider,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext

TENANT = uuid4()
ORG = uuid4()
ENTITY = uuid4()
OPERATION = uuid4()
PROPOSAL = uuid4()
PERIOD = uuid4()
POSTED = uuid4()


def result() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(TENANT),
            "organization_id": str(ORG),
            "legal_entity_id": str(ENTITY),
        },
        "operation_id": str(OPERATION),
        "proposal_id": str(PROPOSAL),
        "proposal_version": 1,
        "outcome": "POSTED",
        "posted_journal_id": str(POSTED),
        "posted_at": datetime.now(UTC).isoformat(),
        "ledger_references": [{"resource_type": "posted_journal", "resource_id": str(POSTED)}],
        "issues": [],
        "producer": {"producer_type": "SERVICE", "name": "role2", "version": "2.0"},
        "correlation": {
            "request_id": str(uuid4()),
            "correlation_id": str(uuid4()),
            "causation_id": None,
        },
    }


@pytest.mark.asyncio
async def test_role2_status_lookup_uses_fixed_authenticated_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/journal-posting-status"
        assert request.headers["x-operation-id"] == str(OPERATION)
        assert request.headers["authorization"].startswith("Bearer ")
        return httpx.Response(200, json=result())

    adapter = Role2Adapter(
        AdapterSecurity(
            base_url="http://role2.test",
            audience="role2",
            environment="test",
            maximum_attempts=1,
        ),
        SignedServiceTokenProvider(issuer="test", subject="backend", secret="x" * 32),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    response = await adapter.posting_status(
        payload={"operation_id": str(OPERATION)},
        tenant_context=EntityTenantContext(
            tenant_id=TENANT, organization_id=ORG, legal_entity_id=ENTITY
        ),
        operation_id=OPERATION,
        correlation_id=uuid4(),
    )
    assert response.outcome == "POSTED"


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, row: object) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        for row in self.added:
            if hasattr(row, "id") and row.id is None:
                row.id = uuid4()
            if hasattr(row, "created_at") and row.created_at is None:
                row.created_at = datetime.now(UTC)
            if isinstance(row, ProgressEvent) and row.progress_event_id is None:
                row.progress_event_id = uuid4()


class FakeRepository:
    def __init__(self, operation: PostingOperation) -> None:
        self.operation = operation
        self.session = FakeSession()
        self.organization_id = ORG
        self.legal_entity_id = ENTITY
        self.period_row: AccountingPeriod | None = None

    def scope_values(self) -> dict[str, UUID]:
        return {"tenant_id": TENANT, "organization_id": ORG, "legal_entity_id": ENTITY}

    async def lock_key(self, namespace: str, value: str) -> None:
        return None

    async def posting(self, operation_id: UUID, *, lock: bool = False) -> PostingOperation | None:
        return self.operation if operation_id == OPERATION else None

    async def projection(
        self, resource_type: str, resource_id: UUID, *, lock: bool = False
    ) -> None:
        return None

    async def latest_audit_hash(self) -> None:
        return None

    async def period(self, period_id: UUID, *, lock: bool = False) -> AccountingPeriod | None:
        return self.period_row if self.period_row and self.period_row.id == period_id else None

    async def statement_by_role2_id(self, snapshot_id: UUID) -> None:
        return None


class StatusRole2:
    async def posting_status(self, **kwargs: Any) -> Any:
        from ledgerai_contracts.v1.accounting import PostingStatusResult

        return PostingStatusResult.model_validate(result())


@pytest.mark.asyncio
async def test_unknown_posting_is_looked_up_and_confirmed_without_reposting() -> None:
    row = PostingOperation(
        tenant_id=TENANT,
        organization_id=ORG,
        legal_entity_id=ENTITY,
        id=uuid4(),
        operation_id=OPERATION,
        journal_proposal_id=PROPOSAL,
        proposal_version=1,
        accounting_period_id=PERIOD,
        state=PostingState.UNKNOWN,
        idempotency_key="posting-recovery-test",
        request_hash="a" * 64,
        requested_by_principal_id=uuid4(),
        correlation_id=uuid4(),
        version=3,
    )
    repository = FakeRepository(row)
    context = AuthorizationContext(
        principal_id=uuid4(),
        external_subject="tester",
        tenant_id=TENANT,
        organization_id=ORG,
        legal_entity_id=ENTITY,
        membership_id=uuid4(),
        roles=frozenset(),
        permissions=frozenset(),
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    service = AssuranceService(
        cast(AssuranceRepository, repository),
        context,
        cast(Role2AssurancePort, StatusRole2()),
    )
    recovered = await service.refresh_posting(OPERATION)
    assert recovered.state == PostingState.CONFIRMED
    assert any(isinstance(item, PostingConfirmation) for item in repository.session.added)
    assert any(isinstance(item, ProvenanceEdge) for item in repository.session.added)
    assert any(isinstance(item, ProgressEvent) for item in repository.session.added)
    assert any(isinstance(item, AuditEvent) for item in repository.session.added)


@pytest.mark.asyncio
async def test_bound_close_confirmation_closes_period_and_projects_progress() -> None:
    from ledgerai_contracts.v1.accounting import PeriodCloseResult

    operation = PostingOperation(
        tenant_id=TENANT,
        organization_id=ORG,
        legal_entity_id=ENTITY,
        id=uuid4(),
        operation_id=OPERATION,
        journal_proposal_id=PROPOSAL,
        proposal_version=1,
        accounting_period_id=PERIOD,
        state=PostingState.CONFIRMED,
        idempotency_key="unused-posting",
        request_hash="a" * 64,
        requested_by_principal_id=uuid4(),
        correlation_id=uuid4(),
    )
    repository = FakeRepository(operation)
    context = AuthorizationContext(
        principal_id=uuid4(),
        external_subject="tester",
        tenant_id=TENANT,
        organization_id=ORG,
        legal_entity_id=ENTITY,
        membership_id=uuid4(),
        roles=frozenset(),
        permissions=frozenset(),
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    service = AssuranceService(cast(AssuranceRepository, repository), context, None)
    period = AccountingPeriod(
        tenant_id=TENANT,
        organization_id=ORG,
        legal_entity_id=ENTITY,
        id=PERIOD,
        period_start=datetime(2026, 1, 1, tzinfo=UTC).date(),
        period_end=datetime(2026, 1, 31, tzinfo=UTC).date(),
        currency="INR",
        state=PeriodState.CLOSING,
        version=3,
    )
    close = CloseRun(
        tenant_id=TENANT,
        organization_id=ORG,
        legal_entity_id=ENTITY,
        id=uuid4(),
        accounting_period_id=PERIOD,
        operation_id=OPERATION,
        state=CloseState.IN_PROGRESS,
        idempotency_key="close-confirm-test",
        request_hash="b" * 64,
        requested_by_principal_id=context.principal_id,
        correlation_id=UUID(context.correlation_id),
        version=2,
    )
    closed_at = datetime.now(UTC)
    close_result = PeriodCloseResult.model_validate(
        {
            "schema_version": "1.0",
            "tenant_context": {
                "tenant_id": str(TENANT),
                "organization_id": str(ORG),
                "legal_entity_id": str(ENTITY),
            },
            "operation_id": str(OPERATION),
            "accounting_period_id": str(PERIOD),
            "outcome": "CLOSED",
            "issues": [],
            "closed_at": closed_at.isoformat(),
            "producer": {"producer_type": "SERVICE", "name": "role2", "version": "2.0"},
            "correlation": {
                "request_id": str(uuid4()),
                "correlation_id": str(uuid4()),
                "causation_id": None,
            },
        }
    )
    await service._apply_close_result(close, period, close_result)
    assert close.state == CloseState.CONFIRMED
    assert period.state == PeriodState.CLOSED
    assert period.closed_at == closed_at
    assert any(isinstance(item, ProgressEvent) for item in repository.session.added)
    assert any(isinstance(item, AuditEvent) for item in repository.session.added)


class StatementRole2:
    async def financial_statement(self, **kwargs: Any) -> Any:
        from ledgerai_contracts.v1.accounting import FinancialStatementSnapshot

        return FinancialStatementSnapshot.model_validate(
            {
                "schema_version": "1.0",
                "snapshot_id": str(uuid4()),
                "tenant_context": {
                    "tenant_id": str(TENANT),
                    "organization_id": str(ORG),
                    "legal_entity_id": str(ENTITY),
                },
                "accounting_period_id": str(PERIOD),
                "statement_type": "TRIAL_BALANCE",
                "currency": "INR",
                "as_of": datetime.now(UTC).isoformat(),
                "status": "AVAILABLE",
                "lines": [
                    {
                        "line_id": "cash",
                        "account_reference": "1100",
                        "label": "Cash",
                        "amount": {"amount": "100.00", "currency": "INR"},
                        "ledger_references": [
                            {"resource_type": "posted_journal", "resource_id": str(POSTED)}
                        ],
                    }
                ],
                "producer": {"producer_type": "SERVICE", "name": "role2", "version": "2.0"},
                "correlation": {
                    "request_id": str(uuid4()),
                    "correlation_id": str(uuid4()),
                    "causation_id": None,
                },
            }
        )


@pytest.mark.asyncio
async def test_available_role2_statement_is_captured_without_recalculation() -> None:
    operation = PostingOperation(
        tenant_id=TENANT,
        organization_id=ORG,
        legal_entity_id=ENTITY,
        id=uuid4(),
        operation_id=OPERATION,
        journal_proposal_id=PROPOSAL,
        proposal_version=1,
        accounting_period_id=PERIOD,
        state=PostingState.CONFIRMED,
        idempotency_key="unused-statement",
        request_hash="a" * 64,
        requested_by_principal_id=uuid4(),
        correlation_id=uuid4(),
    )
    repository = FakeRepository(operation)
    repository.period_row = AccountingPeriod(
        tenant_id=TENANT,
        organization_id=ORG,
        legal_entity_id=ENTITY,
        id=PERIOD,
        period_start=datetime(2026, 1, 1, tzinfo=UTC).date(),
        period_end=datetime(2026, 1, 31, tzinfo=UTC).date(),
        currency="INR",
        state=PeriodState.CLOSED,
    )
    context = AuthorizationContext(
        principal_id=uuid4(),
        external_subject="tester",
        tenant_id=TENANT,
        organization_id=ORG,
        legal_entity_id=ENTITY,
        membership_id=uuid4(),
        roles=frozenset(),
        permissions=frozenset(),
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    service = AssuranceService(
        cast(AssuranceRepository, repository),
        context,
        cast(Role2AssurancePort, StatementRole2()),
    )
    snapshot = await service.request_statement(PERIOD, "TRIAL_BALANCE")
    assert snapshot.statement_type == "TRIAL_BALANCE"
    lines = [item for item in repository.session.added if isinstance(item, FinancialStatementLine)]
    assert len(lines) == 1
    assert str(lines[0].amount) == "100.00"
    assert any(isinstance(item, StatementRow) for item in repository.session.added)
    assert any(isinstance(item, AuditEvent) for item in repository.session.added)
