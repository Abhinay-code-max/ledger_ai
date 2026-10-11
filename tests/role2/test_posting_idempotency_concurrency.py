"""Tests for posting idempotency, conflict detection, and concurrent execution."""

from __future__ import annotations

import asyncio
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
from ledgerai_role2.domain.state_machine import IdempotencyConflictError
from ledgerai_role2.service import Role2Service

TENANT_CTX = EntityTenantContext(
    tenant_id=UUID("00000000-0000-4000-8000-000000000001"),
    organization_id=UUID("00000000-0000-4000-8000-000000000002"),
    legal_entity_id=UUID("00000000-0000-4000-8000-000000000003"),
)


async def create_test_service() -> Role2Service:
    repo = InMemoryRole2Repository(TENANT_CTX)
    svc = Role2Service(repo)
    # Seed COA
    await repo.save_account(
        Account.create("1010", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    await repo.save_account(
        Account.create("4010", "Sales", AccountType.REVENUE, "INR", NormalBalance.CREDIT)
    )
    # Seed Open Period
    await repo.save_period(
        period_id=UUID("00000000-0000-4000-8000-000000000020"),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        state=PeriodStatus.OPEN,
    )
    return svc


def sample_lines() -> list[DomainJournalLine]:
    ev = [
        ProvenanceReference(
            source_document_id=uuid4(), document_version="1", evidence_hash="c" * 64
        )
    ]
    return [
        DomainJournalLine(
            line_id=uuid4(),
            account_reference="1010",
            direction=Direction.DEBIT,
            amount=Decimal("1000.00"),
            currency="INR",
            source_evidence=ev,
        ),
        DomainJournalLine(
            line_id=uuid4(),
            account_reference="4010",
            direction=Direction.CREDIT,
            amount=Decimal("1000.00"),
            currency="INR",
            source_evidence=ev,
        ),
    ]


@pytest.mark.asyncio
async def test_duplicate_posting_is_strictly_idempotent() -> None:
    service = await create_test_service()
    op_id = uuid4()
    prop_id = uuid4()
    period_id = UUID("00000000-0000-4000-8000-000000000020")
    payload = {"op": str(op_id), "amount": "1000.00"}

    # First call
    res1 = await service.post_journal(
        operation_id=op_id,
        proposal_id=prop_id,
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload=payload,
        inline_lines=sample_lines(),
        journal_date=date(2026, 1, 15),
        currency="INR",
    )
    assert res1.outcome == "POSTED"
    assert res1.posted_journal_id is not None
    assert res1.posted_at is not None

    # Duplicate call with identical payload
    res2 = await service.post_journal(
        operation_id=op_id,
        proposal_id=prop_id,
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload=payload,
        inline_lines=sample_lines(),
        journal_date=date(2026, 1, 15),
        currency="INR",
    )
    assert res2.outcome == "POSTED"
    assert res2.posted_journal_id == res1.posted_journal_id
    assert res2.posted_at == res1.posted_at

    # Verify only ONE journal was stored
    journals = await service.repo.list_domain_journals_for_period(period_id)
    assert len(journals) == 1


@pytest.mark.asyncio
async def test_same_operation_id_different_payload_raises_conflict() -> None:
    service = await create_test_service()
    op_id = uuid4()
    prop_id = uuid4()
    period_id = UUID("00000000-0000-4000-8000-000000000020")

    payload1 = {"op": str(op_id), "amount": "1000.00"}
    payload2 = {"op": str(op_id), "amount": "2000.00"}  # Changed payload!

    await service.post_journal(
        operation_id=op_id,
        proposal_id=prop_id,
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload=payload1,
        inline_lines=sample_lines(),
        journal_date=date(2026, 1, 15),
        currency="INR",
    )

    with pytest.raises(IdempotencyConflictError):
        await service.post_journal(
            operation_id=op_id,
            proposal_id=prop_id,
            proposal_version=1,
            accounting_period_id=period_id,
            raw_payload=payload2,
            inline_lines=sample_lines(),
            journal_date=date(2026, 1, 15),
            currency="INR",
        )


@pytest.mark.asyncio
async def test_concurrent_posting_attempts_produce_single_journal() -> None:
    service = await create_test_service()
    op_id = uuid4()
    prop_id = uuid4()
    period_id = UUID("00000000-0000-4000-8000-000000000020")
    payload = {"op": str(op_id), "amount": "1000.00"}

    # Simulate 5 concurrent postings with the same operation_id and payload
    tasks = [
        service.post_journal(
            operation_id=op_id,
            proposal_id=prop_id,
            proposal_version=1,
            accounting_period_id=period_id,
            raw_payload=payload,
            inline_lines=sample_lines(),
            journal_date=date(2026, 1, 15),
            currency="INR",
        )
        for _ in range(5)
    ]

    results = await asyncio.gather(*tasks)

    # All results must be POSTED with the same posted_journal_id
    first_journal_id = results[0].posted_journal_id
    for r in results:
        assert r.outcome == "POSTED"
        assert r.posted_journal_id == first_journal_id

    # Exactly 1 journal in repository
    journals = await service.repo.list_domain_journals_for_period(period_id)
    assert len(journals) == 1
