"""Tests for journal reversal, correcting entries, and immutable ledger history."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from ledgerai_contracts.v1.common import ProvenanceReference
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role2.database.in_memory import InMemoryRole2Repository
from ledgerai_role2.domain.calculator import calculate_trial_balance
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
        Account.create("5010", "Hosting", AccountType.EXPENSE, "INR", NormalBalance.DEBIT)
    )
    await repo.save_period(
        period_id=UUID("00000000-0000-4000-8000-000000000020"),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        state=PeriodStatus.OPEN,
    )
    return svc


def valid_lines(amount: Decimal = Decimal("500.00")) -> list[DomainJournalLine]:
    ev = [
        ProvenanceReference(
            source_document_id=uuid4(), document_version="1", evidence_hash="a" * 64
        )
    ]
    return [
        DomainJournalLine(uuid4(), "5010", Direction.DEBIT, amount, "INR", source_evidence=ev),
        DomainJournalLine(uuid4(), "1010", Direction.CREDIT, amount, "INR", source_evidence=ev),
    ]


@pytest.mark.asyncio
async def test_successful_reversal_inverts_lines_and_nets_to_zero() -> None:
    service = await create_test_service()
    period_id = UUID("00000000-0000-4000-8000-000000000020")

    # Post original journal
    orig_post = await service.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload={"op": "orig"},
        inline_lines=valid_lines(Decimal("500.00")),
        journal_date=date(2026, 1, 10),
        currency="INR",
    )
    assert orig_post.outcome == "POSTED"
    orig_j_id = UUID(orig_post.posted_journal_id)

    # Post reversal
    rev_op_id = uuid4()
    rev_res = await service.reverse_posted_journal(
        operation_id=rev_op_id,
        journal_id=orig_j_id,
        accounting_period_id=period_id,
        reversal_date=date(2026, 1, 11),
        reason="Erroneous charge correction",
    )
    assert rev_res.outcome == "POSTED"
    assert rev_res.posted_journal_id is not None
    rev_j_id = UUID(rev_res.posted_journal_id)
    assert rev_j_id != orig_j_id

    # Check that original journal is flagged as reversed
    orig_db = await service.repo.get_journal(orig_j_id)
    assert orig_db is not None
    assert orig_db.is_reversed is True

    # Check trial balance net effect: lines must net to zero!
    accounts_map = await service._load_accounts_map()
    journals = await service.repo.list_domain_journals_for_period(period_id)
    tb = calculate_trial_balance(
        accounts_map,
        journals,
        accounting_period_id=period_id,
        as_of=date.today(),
        currency="INR",
    )

    cash_line = next((line for line in tb.lines if line.account_reference == "1010"), None)
    hosting_line = next((line for line in tb.lines if line.account_reference == "5010"), None)
    if cash_line:
        assert cash_line.amount == Decimal("0.00")
    if hosting_line:
        assert hosting_line.amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_reversal_of_already_reversed_journal_rejected() -> None:
    service = await create_test_service()
    period_id = UUID("00000000-0000-4000-8000-000000000020")

    orig_post = await service.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload={"op": "orig"},
        inline_lines=valid_lines(Decimal("200.00")),
        journal_date=date(2026, 1, 10),
        currency="INR",
    )
    orig_j_id = UUID(orig_post.posted_journal_id)

    # First reversal succeeds
    await service.reverse_posted_journal(
        operation_id=uuid4(),
        journal_id=orig_j_id,
        accounting_period_id=period_id,
        reversal_date=date(2026, 1, 11),
        reason="First reversal",
    )

    # Second reversal of same journal is rejected
    second_rev = await service.reverse_posted_journal(
        operation_id=uuid4(),
        journal_id=orig_j_id,
        accounting_period_id=period_id,
        reversal_date=date(2026, 1, 12),
        reason="Duplicate reversal attempt",
    )
    assert second_rev.outcome == "REJECTED"
    assert any(i.code == "ALREADY_REVERSED" for i in second_rev.issues)


@pytest.mark.asyncio
async def test_reversal_of_nonexistent_journal_rejected() -> None:
    service = await create_test_service()
    period_id = UUID("00000000-0000-4000-8000-000000000020")

    res = await service.reverse_posted_journal(
        operation_id=uuid4(),
        journal_id=uuid4(),
        accounting_period_id=period_id,
        reversal_date=date(2026, 1, 11),
        reason="Nonexistent",
    )
    assert res.outcome == "REJECTED"
    assert any(i.code == "JOURNAL_NOT_FOUND" for i in res.issues)
