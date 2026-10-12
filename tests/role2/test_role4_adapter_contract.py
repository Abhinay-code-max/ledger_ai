"""Contract integration tests between Role 4's Role2Adapter and the Role 2 service."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from ledgerai_backend.integration.adapters import (
    AdapterSecurity,
    Role2Adapter,
    SignedServiceTokenProvider,
)
from ledgerai_contracts.v1.common import ProvenanceReference
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role2.api.app import create_role2_app
from ledgerai_role2.config import Role2Settings
from ledgerai_role2.domain.models import Account, AccountType, NormalBalance, PeriodStatus

SECRET = "x" * 32
ISSUER = "ledgerai-backend"
AUDIENCE = "role2"
TENANT = EntityTenantContext(
    tenant_id=UUID("10000000-0000-4000-8000-000000000001"),
    organization_id=UUID("10000000-0000-4000-8000-000000000002"),
    legal_entity_id=UUID("10000000-0000-4000-8000-000000000003"),
)


@pytest.fixture
def app() -> Any:
    settings = Role2Settings(
        service_token_secret=SECRET,  # type: ignore[arg-type]
        service_token_audience=AUDIENCE,
        service_token_issuer=ISSUER,
    )
    return create_role2_app(settings)


@pytest.fixture
def role2_adapter(app: Any) -> Role2Adapter:
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://role2.test",
    )
    token_provider = SignedServiceTokenProvider(
        issuer=ISSUER,
        subject="service:backend",
        secret=SECRET,
    )
    security = AdapterSecurity(
        base_url="http://role2.test",
        audience=AUDIENCE,
        environment="test",
        maximum_attempts=1,
    )
    return Role2Adapter(security, token_provider, client=client)


@pytest.mark.asyncio
async def test_full_role4_adapter_lifecycle(app: Any, role2_adapter: Role2Adapter) -> None:
    # 1. Setup accounts and period via internal repo
    repo = app.state.get_repository(TENANT)
    await repo.save_account(
        Account.create("1010", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    await repo.save_account(
        Account.create("4010", "Sales", AccountType.REVENUE, "INR", NormalBalance.CREDIT)
    )
    period_id = uuid4()
    await repo.save_period(
        period_id=period_id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        state=PeriodStatus.OPEN,
    )

    op_id = uuid4()
    prop_id = uuid4()
    corr_id = uuid4()

    ev = [
        ProvenanceReference(
            source_document_id=uuid4(), document_version="1", evidence_hash="e" * 64
        )
    ]
    lines = [
        {
            "line_id": str(uuid4()),
            "account_reference": "1010",
            "direction": "DEBIT",
            "amount": {"amount": "750.00", "currency": "INR"},
            "description": "Cash sale",
            "source_evidence": [e.model_dump(mode="json") for e in ev],
        },
        {
            "line_id": str(uuid4()),
            "account_reference": "4010",
            "direction": "CREDIT",
            "amount": {"amount": "750.00", "currency": "INR"},
            "description": "Revenue",
            "source_evidence": [e.model_dump(mode="json") for e in ev],
        },
    ]

    # Step 1: request_posting_validation
    acceptance = await role2_adapter.request_posting_validation(
        payload={
            "proposal_id": str(prop_id),
            "proposal_version": 1,
            "proposed_journal_date": "2026-01-15",
            "currency": "INR",
            "explanation": "Cash sale",
            "lines": lines,
            "source_evidence": [e.model_dump(mode="json") for e in ev],
        },
        tenant_context=TENANT,
        operation_id=op_id,
        correlation_id=corr_id,
    )
    assert acceptance.accepted is True
    assert acceptance.operation_id == op_id

    posting_request_payload = {
        "schema_version": "1.0",
        "tenant_context": TENANT.model_dump(mode="json"),
        "operation_id": str(op_id),
        "proposal": {
            "resource_type": "journal_proposal",
            "resource_id": str(prop_id),
            "resource_version": "1",
        },
        "proposal_version": 1,
        "accounting_period_id": str(period_id),
        "requested_at": datetime.now(UTC).isoformat(),
        "producer": {"producer_type": "SERVICE", "name": "backend", "version": "1.3.0"},
        "correlation": {
            "request_id": str(op_id),
            "correlation_id": str(corr_id),
            "causation_id": None,
        },
    }

    # Step 2: validate_posting
    validation = await role2_adapter.validate_posting(
        payload=posting_request_payload,
        tenant_context=TENANT,
        operation_id=op_id,
        correlation_id=corr_id,
    )
    assert validation.outcome == "VALIDATED"
    assert len(validation.issues) == 0

    # Step 3: post_journal
    post_result = await role2_adapter.post_journal(
        payload=posting_request_payload,
        tenant_context=TENANT,
        operation_id=op_id,
        correlation_id=corr_id,
    )
    assert post_result.outcome == "POSTED"
    assert post_result.posted_journal_id is not None
    assert post_result.posted_at is not None
    assert len(post_result.ledger_references) == 1

    # Step 4: posting_status
    status_result = await role2_adapter.posting_status(
        payload={"operation_id": str(op_id)},
        tenant_context=TENANT,
        operation_id=op_id,
        correlation_id=corr_id,
    )
    assert status_result.outcome == "POSTED"
    assert status_result.posted_journal_id == post_result.posted_journal_id

    # Step 5: validate_period_close
    close_op_id = uuid4()
    close_val = await role2_adapter.validate_period_close(
        payload={"accounting_period_id": str(period_id)},
        tenant_context=TENANT,
        operation_id=close_op_id,
        correlation_id=corr_id,
    )
    assert close_val.outcome == "VALIDATED"

    # Step 6: close_period
    close_result = await role2_adapter.close_period(
        payload={"accounting_period_id": str(period_id)},
        tenant_context=TENANT,
        operation_id=close_op_id,
        correlation_id=corr_id,
    )
    assert close_result.outcome == "CLOSED"
    assert close_result.closed_at is not None

    # Step 7: period_close_status
    close_status = await role2_adapter.period_close_status(
        payload={"operation_id": str(close_op_id)},
        tenant_context=TENANT,
        operation_id=close_op_id,
        correlation_id=corr_id,
    )
    assert close_status.outcome == "CLOSED"
    assert close_status.closed_at == close_result.closed_at

    # Step 8: financial_statement
    stmt_op_id = uuid4()
    tb_snapshot = await role2_adapter.financial_statement(
        payload={
            "schema_version": "1.0",
            "tenant_context": TENANT.model_dump(mode="json"),
            "operation_id": str(stmt_op_id),
            "accounting_period_id": str(period_id),
            "statement_type": "TRIAL_BALANCE",
            "as_of": datetime.now(UTC).isoformat(),
            "correlation": {
                "request_id": str(stmt_op_id),
                "correlation_id": str(corr_id),
                "causation_id": None,
            },
        },
        tenant_context=TENANT,
        operation_id=stmt_op_id,
        correlation_id=corr_id,
    )
    assert tb_snapshot.status == "AVAILABLE"
    assert tb_snapshot.statement_type == "TRIAL_BALANCE"
    assert len(tb_snapshot.lines) >= 2
