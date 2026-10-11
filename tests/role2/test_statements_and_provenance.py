"""Tests for financial statements mathematical equations and provenance tracing."""

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
    # Assets
    await repo.save_account(
        Account.create("1010", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    await repo.save_account(
        Account.create("1020", "Receivables", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    # Liabilities
    await repo.save_account(
        Account.create("2010", "Payables", AccountType.LIABILITY, "INR", NormalBalance.CREDIT)
    )
    # Equity
    await repo.save_account(
        Account.create("3010", "Capital", AccountType.EQUITY, "INR", NormalBalance.CREDIT)
    )
    # Revenues & Expenses
    await repo.save_account(
        Account.create("4010", "Revenue", AccountType.REVENUE, "INR", NormalBalance.CREDIT)
    )
    await repo.save_account(
        Account.create("5010", "Expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT)
    )

    await repo.save_period(
        period_id=UUID("00000000-0000-4000-8000-000000000020"),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        state=PeriodStatus.OPEN,
    )
    return svc


def ev() -> list[ProvenanceReference]:
    return [
        ProvenanceReference(
            source_document_id=uuid4(), document_version="1", evidence_hash="9" * 64
        )
    ]


@pytest.mark.asyncio
async def test_trial_balance_pl_and_balance_sheet_equations() -> None:
    service = await create_test_service()
    period_id = UUID("00000000-0000-4000-8000-000000000020")

    # Entry 1: Capital injection (DR Cash 10000, CR Capital 10000)
    await service.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload={"op": "1"},
        inline_lines=[
            DomainJournalLine(
                uuid4(), "1010", Direction.DEBIT, Decimal("10000.00"), "INR", source_evidence=ev()
            ),
            DomainJournalLine(
                uuid4(), "3010", Direction.CREDIT, Decimal("10000.00"), "INR", source_evidence=ev()
            ),
        ],
        journal_date=date(2026, 1, 5),
        currency="INR",
    )

    # Entry 2: Revenue earned on credit (DR Receivables 4000, CR Revenue 4000)
    await service.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload={"op": "2"},
        inline_lines=[
            DomainJournalLine(
                uuid4(), "1020", Direction.DEBIT, Decimal("4000.00"), "INR", source_evidence=ev()
            ),
            DomainJournalLine(
                uuid4(), "4010", Direction.CREDIT, Decimal("4000.00"), "INR", source_evidence=ev()
            ),
        ],
        journal_date=date(2026, 1, 10),
        currency="INR",
    )

    # Entry 3: Expense incurred on credit (DR Expense 1500, CR Payables 1500)
    await service.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_id,
        raw_payload={"op": "3"},
        inline_lines=[
            DomainJournalLine(
                uuid4(), "5010", Direction.DEBIT, Decimal("1500.00"), "INR", source_evidence=ev()
            ),
            DomainJournalLine(
                uuid4(), "2010", Direction.CREDIT, Decimal("1500.00"), "INR", source_evidence=ev()
            ),
        ],
        journal_date=date(2026, 1, 15),
        currency="INR",
    )

    now = datetime.now(UTC)

    # 1. Trial Balance Check
    tb = await service.generate_statement(
        operation_id=uuid4(),
        accounting_period_id=period_id,
        statement_type="TRIAL_BALANCE",
        as_of=now,
        currency="INR",
    )
    total_debits = next(
        line for line in tb.lines if line.account_reference == "TOTAL_DEBITS"
    ).amount.amount
    total_credits = next(
        line for line in tb.lines if line.account_reference == "TOTAL_CREDITS"
    ).amount.amount
    assert total_debits == total_credits
    assert total_debits == Decimal("15500.00")

    # 2. Profit & Loss Check
    pl = await service.generate_statement(
        operation_id=uuid4(),
        accounting_period_id=period_id,
        statement_type="PROFIT_AND_LOSS",
        as_of=now,
        currency="INR",
    )
    tot_rev = next(
        line for line in pl.lines if line.account_reference == "TOTAL_REVENUE"
    ).amount.amount
    tot_exp = next(
        line for line in pl.lines if line.account_reference == "TOTAL_EXPENSES"
    ).amount.amount
    net_inc = next(
        line for line in pl.lines if line.account_reference == "NET_INCOME"
    ).amount.amount
    assert tot_rev == Decimal("4000.00")
    assert tot_exp == Decimal("1500.00")
    assert net_inc == Decimal("2500.00")
    assert net_inc == tot_rev - tot_exp

    # 3. Balance Sheet Check: Assets == Liabilities + Equity
    bs = await service.generate_statement(
        operation_id=uuid4(),
        accounting_period_id=period_id,
        statement_type="BALANCE_SHEET",
        as_of=now,
        currency="INR",
    )
    tot_ast = next(
        line for line in bs.lines if line.account_reference == "TOTAL_ASSETS"
    ).amount.amount
    tot_lia = next(
        line for line in bs.lines if line.account_reference == "TOTAL_LIABILITIES"
    ).amount.amount
    tot_eq = next(
        line for line in bs.lines if line.account_reference == "TOTAL_EQUITY"
    ).amount.amount
    tot_lia_eq = next(
        line for line in bs.lines if line.account_reference == "TOTAL_LIABILITIES_AND_EQUITY"
    ).amount.amount

    # Assets = Cash (10000) + Receivables (4000) = 14000
    assert tot_ast == Decimal("14000.00")
    # Liabilities = Payables (1500)
    assert tot_lia == Decimal("1500.00")
    # Equity = Capital (10000) + Net Income (2500) = 12500
    assert tot_eq == Decimal("12500.00")
    # Balance Sheet Equation:
    assert tot_ast == tot_lia + tot_eq
    assert tot_ast == tot_lia_eq
    assert tot_ast - (tot_lia + tot_eq) == Decimal("0.00")

    # Provenance check: lines must have ledger references
    for line in tb.lines:
        assert len(line.ledger_references) > 0
    for line in bs.lines:
        assert len(line.ledger_references) > 0
