"""Tests for accounting period boundaries and period close confirmation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from ledgerai_contracts.v1.common import ProvenanceReference
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role2.database.in_memory import InMemoryRole2Repository
from ledgerai_role2.domain.models import (
    Account,
    AccountType,
    Direction,
    DomainJournalLine,
    NormalBalance,
    PeriodStatus,
)
from ledgerai_role2.service import Role2Service

TENANT_CTX = EntityTenantContext(
    tenant_id=UUID("00000000-0000-4000-8000-000000000001"),
    organization_id=UUID("00000000-0000-4000-8000-000000000002"),
    legal_entity_id=UUID("00000000-0000-4000-8000-000000000003"),
)


async def create_test_service() -> Role2Service:
    repo = InMemoryRole2Repository(TENANT_CTX)
    svc = Role2Service(repo)
    await repo.save_account(
        Account.create("1010", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    await repo.save_account(
        Account.create("4010", "Sales", AccountType.REVENUE, "INR", NormalBalance.CREDIT)
    )
    await repo.save_period(
        period_id=UUID("00000000-0000-4000-8000-000000000020"),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        state=PeriodStatus.OPEN,
    )
    return svc


def valid_lines() -> list[DomainJournalLine]:
    ev = [
        ProvenanceReference(
            source_document_id=uuid4(), document_version="1", evidence_hash="f" * 64
        )
    ]
    return [
        DomainJournalLine(
            uuid4(), "1010", Direction.DEBIT, Decimal("100.00"), "INR", source_evidence=ev
        ),
        DomainJournalLine(
            uuid4(), "4010", Direction.CREDIT, Decimal("100.00"), "INR", source_evidence=ev
        ),
    ]


@pytest.mark.asyncio
async def test_posting_before_period_start_rejected() -> None:
    service = await create_test_service()
    period_id = UUID("00000000-0000-4000-8000-000000000020")
    res = await service.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload={"op": "before"},
        inline_lines=valid_lines(),
        journal_date=date(2025, 12, 31),  # Day before period start!
        currency="INR",
    )
    assert res.outcome == "REJECTED"
    assert any(i.code == "POSTING_DATE_OUTSIDE_PERIOD" for i in res.issues)


@pytest.mark.asyncio
async def test_posting_after_period_end_rejected() -> None:
    service = await create_test_service()
    period_id = UUID("00000000-0000-4000-8000-000000000020")
    res = await service.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload={"op": "after"},
        inline_lines=valid_lines(),
        journal_date=date(2026, 2, 1),  # Day after period end!
        currency="INR",
    )
    assert res.outcome == "REJECTED"
    assert any(i.code == "POSTING_DATE_OUTSIDE_PERIOD" for i in res.issues)


@pytest.mark.asyncio
async def test_posting_into_closed_period_rejected() -> None:
    service = await create_test_service()
    closed_period_id = uuid4()
    await service.repo.save_period(
        period_id=closed_period_id,
        period_start=date(2025, 12, 1),
        period_end=date(2025, 12, 31),
        state=PeriodStatus.CLOSED,
    )

    res = await service.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=closed_period_id,
        raw_payload={"op": "closed"},
        inline_lines=valid_lines(),
        journal_date=date(2025, 12, 15),
        currency="INR",
    )
    assert res.outcome == "REJECTED"
    assert any(i.code == "PERIOD_NOT_OPEN" for i in res.issues)


@pytest.mark.asyncio
async def test_period_close_lifecycle_and_idempotency() -> None:
    service = await create_test_service()
    period_id = UUID("00000000-0000-4000-8000-000000000020")

    # Post one valid journal first
    post_res = await service.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload={"op": "post1"},
        inline_lines=valid_lines(),
        journal_date=date(2026, 1, 15),
        currency="INR",
    )
    assert post_res.outcome == "POSTED"

    # Validate close
    val_res = await service.validate_period_close(
        operation_id=uuid4(),
        accounting_period_id=period_id,
    )
    assert val_res.outcome == "VALIDATED"

    # Close period
    close_op_id = uuid4()
    close_payload = {"op": str(close_op_id), "period": str(period_id)}
    close_res = await service.close_period(
        operation_id=close_op_id,
        accounting_period_id=period_id,
        raw_payload=close_payload,
    )
    assert close_res.outcome == "CLOSED"
    assert close_res.closed_at is not None

    # Verify period state in repo
    period = await service.repo.get_period(period_id)
    assert period is not None
    assert period.state == PeriodStatus.CLOSED

    # Idempotent re-close call
    close_res_dup = await service.close_period(
        operation_id=close_op_id,
        accounting_period_id=period_id,
        raw_payload=close_payload,
    )
    assert close_res_dup.outcome == "CLOSED"
    assert close_res_dup.closed_at == close_res.closed_at

    # New postings into now-closed period must be rejected
    reject_res = await service.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload={"op": "after_close"},
        inline_lines=valid_lines(),
        journal_date=date(2026, 1, 20),
        currency="INR",
    )
    assert reject_res.outcome == "REJECTED"
    assert any(i.code == "PERIOD_NOT_OPEN" for i in reject_res.issues)
