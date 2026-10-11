"""Tests for unknown outcome recovery and status lookup without re-posting."""

from __future__ import annotations

from datetime import UTC, date, datetime
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
    DomainJournal,
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


@pytest.mark.asyncio
async def test_status_lookup_recovers_posted_journal_without_reposting() -> None:
    service = await create_test_service()
    op_id = uuid4()
    prop_id = uuid4()
    period_id = UUID("00000000-0000-4000-8000-000000000020")
    payload = {"op": str(op_id), "amount": "500.00"}

    ev = [
        ProvenanceReference(
            source_document_id=uuid4(), document_version="1", evidence_hash="d" * 64
        )
    ]
    lines = [
        DomainJournalLine(
            uuid4(), "1010", Direction.DEBIT, Decimal("500.00"), "INR", source_evidence=ev
        ),
        DomainJournalLine(
            uuid4(), "4010", Direction.CREDIT, Decimal("500.00"), "INR", source_evidence=ev
        ),
    ]

    # Perform initial post
    res = await service.post_journal(
        operation_id=op_id,
        proposal_id=prop_id,
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload=payload,
        inline_lines=lines,
        journal_date=date(2026, 1, 10),
        currency="INR",
    )
    assert res.outcome == "POSTED"

    # Status lookup simulates recovery after client timeout
    status_res = await service.get_posting_status(operation_id=op_id)
    assert status_res.outcome == "POSTED"
    assert status_res.posted_journal_id == res.posted_journal_id
    assert status_res.posted_at == res.posted_at
    assert len(status_res.ledger_references) == 1

    # Verify no new journal was created
    journals = await service.repo.list_domain_journals_for_period(period_id)
    assert len(journals) == 1


@pytest.mark.asyncio
async def test_status_lookup_for_unknown_operation_returns_unknown() -> None:
    service = await create_test_service()
    unknown_op_id = uuid4()

    status_res = await service.get_posting_status(operation_id=unknown_op_id)
    assert status_res.outcome == "UNKNOWN"
    assert any(i.code == "OPERATION_NOT_FOUND" for i in status_res.issues)


@pytest.mark.asyncio
async def test_recovery_from_orphaned_journal_without_operation_row() -> None:
    service = await create_test_service()
    op_id = uuid4()
    j_id = uuid4()
    period_id = UUID("00000000-0000-4000-8000-000000000020")

    ev = [
        ProvenanceReference(
            source_document_id=uuid4(), document_version="1", evidence_hash="e" * 64
        )
    ]
    lines = [
        DomainJournalLine(
            uuid4(), "1010", Direction.DEBIT, Decimal("250.00"), "INR", source_evidence=ev
        ),
        DomainJournalLine(
            uuid4(), "4010", Direction.CREDIT, Decimal("250.00"), "INR", source_evidence=ev
        ),
    ]

    # Directly insert a journal as if service died right after journal insert
    # but before operation record update
    domain_j = DomainJournal(
        journal_id=j_id,
        operation_id=op_id,
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_id,
        journal_date=date(2026, 1, 10),
        currency="INR",
        explanation="Orphaned recovery test",
        lines=lines,
        posted_at=datetime.now(UTC),
    )
    await service.repo.save_journal_with_lines(domain_j)

    # Status lookup should detect the existing journal by operation_id and return POSTED!
    status_res = await service.get_posting_status(operation_id=op_id)
    assert status_res.outcome == "POSTED"
    assert status_res.posted_journal_id == str(j_id)
