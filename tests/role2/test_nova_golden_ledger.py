"""Synthetic NOVA golden ledger test suite verifying complete enterprise accounting cycle."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from ledgerai_role2.database.in_memory import InMemoryRole2Repository
from ledgerai_role2.domain.models import PeriodStatus
from ledgerai_role2.nova.golden_ledger import (
    ERRONEOUS_LEGAL_LINES,
    EXPECTED_NOVA_FIGURES,
    HOSTING_EXPENSE_LINES,
    INVOICE_BILLING_LINES,
    NOVA_ACCOUNTS,
    NOVA_PERIOD_END,
    NOVA_PERIOD_ID,
    NOVA_PERIOD_START,
    NOVA_TENANT_CONTEXT,
    OPENING_BALANCE_LINES,
    PAYMENT_COLLECTION_LINES,
    REPLACEMENT_LEGAL_LINES,
    TOOLING_EXPENSE_LINES,
    VENDOR_PAYOUT_LINES,
    nova_id,
)
from ledgerai_role2.service import Role2Service


async def setup_nova_service() -> Role2Service:
    repo = InMemoryRole2Repository(NOVA_TENANT_CONTEXT)
    service = Role2Service(repo)

    # 1. Initialize Chart of Accounts
    for account in NOVA_ACCOUNTS:
        await repo.save_account(account)

    # 2. Initialize Accounting Period
    await repo.save_period(
        period_id=NOVA_PERIOD_ID,
        period_start=NOVA_PERIOD_START,
        period_end=NOVA_PERIOD_END,
        state=PeriodStatus.OPEN,
    )
    return service


@pytest.mark.asyncio
async def test_nova_synthetic_golden_ledger_full_cycle() -> None:
    service = await setup_nova_service()

    # -------------------------------------------------------------
    # 1. Opening Balances (2026-01-01)
    # -------------------------------------------------------------
    op_open = nova_id("nova:op:opening")
    j_open = await service.post_journal(
        operation_id=op_open,
        proposal_id=nova_id("nova:prop:opening"),
        proposal_version=1,
        accounting_period_id=NOVA_PERIOD_ID,
        raw_payload={"scenario": "opening_balance"},
        inline_lines=OPENING_BALANCE_LINES,
        journal_date=date(2026, 1, 1),
        currency="INR",
        explanation="FY 2026 Opening Balances",
    )
    assert j_open.outcome == "POSTED"

    # -------------------------------------------------------------
    # 2. Client Billing Invoice #INV-2026-001 (2026-01-10)
    # -------------------------------------------------------------
    op_bill = nova_id("nova:op:billing")
    j_bill = await service.post_journal(
        operation_id=op_bill,
        proposal_id=nova_id("nova:prop:billing"),
        proposal_version=1,
        accounting_period_id=NOVA_PERIOD_ID,
        raw_payload={"scenario": "billing"},
        inline_lines=INVOICE_BILLING_LINES,
        journal_date=date(2026, 1, 10),
        currency="INR",
        explanation="Client billing INV-2026-001",
    )
    assert j_bill.outcome == "POSTED"

    # -------------------------------------------------------------
    # 3. AWS Vendor Hosting Bill (2026-01-12)
    # -------------------------------------------------------------
    op_host = nova_id("nova:op:hosting")
    j_host = await service.post_journal(
        operation_id=op_host,
        proposal_id=nova_id("nova:prop:hosting"),
        proposal_version=1,
        accounting_period_id=NOVA_PERIOD_ID,
        raw_payload={"scenario": "hosting"},
        inline_lines=HOSTING_EXPENSE_LINES,
        journal_date=date(2026, 1, 12),
        currency="INR",
        explanation="AWS Cloud infrastructure hosting",
    )
    assert j_host.outcome == "POSTED"

    # -------------------------------------------------------------
    # 4. Client Payment Received via Bank (2026-01-15)
    # -------------------------------------------------------------
    op_recv = nova_id("nova:op:recv")
    j_recv = await service.post_journal(
        operation_id=op_recv,
        proposal_id=nova_id("nova:prop:recv"),
        proposal_version=1,
        accounting_period_id=NOVA_PERIOD_ID,
        raw_payload={"scenario": "receipt"},
        inline_lines=PAYMENT_COLLECTION_LINES,
        journal_date=date(2026, 1, 15),
        currency="INR",
        explanation="Collection against INV-2026-001",
    )
    assert j_recv.outcome == "POSTED"

    # -------------------------------------------------------------
    # 5. Tooling Subscription Bill (2026-01-18)
    # -------------------------------------------------------------
    op_tool = nova_id("nova:op:tooling")
    j_tool = await service.post_journal(
        operation_id=op_tool,
        proposal_id=nova_id("nova:prop:tooling"),
        proposal_version=1,
        accounting_period_id=NOVA_PERIOD_ID,
        raw_payload={"scenario": "tooling"},
        inline_lines=TOOLING_EXPENSE_LINES,
        journal_date=date(2026, 1, 18),
        currency="INR",
        explanation="Developer tooling IDE licenses",
    )
    assert j_tool.outcome == "POSTED"

    # -------------------------------------------------------------
    # 6. Erroneous Legal Expense Entry (2026-01-20)
    # -------------------------------------------------------------
    op_err = nova_id("nova:op:err_legal")
    j_err = await service.post_journal(
        operation_id=op_err,
        proposal_id=nova_id("nova:prop:err_legal"),
        proposal_version=1,
        accounting_period_id=NOVA_PERIOD_ID,
        raw_payload={"scenario": "erroneous_legal"},
        inline_lines=ERRONEOUS_LEGAL_LINES,
        journal_date=date(2026, 1, 20),
        currency="INR",
        explanation="Draft erroneous advisory charge",
    )
    assert j_err.outcome == "POSTED"
    erroneous_j_id = UUID(j_err.posted_journal_id)

    # -------------------------------------------------------------
    # 7. Reversal of Erroneous Legal Entry (2026-01-21)
    # -------------------------------------------------------------
    op_rev = nova_id("nova:op:rev_legal")
    j_rev = await service.reverse_posted_journal(
        operation_id=op_rev,
        journal_id=erroneous_j_id,
        accounting_period_id=NOVA_PERIOD_ID,
        reversal_date=date(2026, 1, 21),
        reason="Correction of erroneous draft legal bill",
    )
    assert j_rev.outcome == "POSTED"

    # -------------------------------------------------------------
    # 8. Replacement Legal Advisory Retainer (2026-01-22)
    # -------------------------------------------------------------
    op_corr = nova_id("nova:op:corr_legal")
    j_corr = await service.post_journal(
        operation_id=op_corr,
        proposal_id=nova_id("nova:prop:corr_legal"),
        proposal_version=1,
        accounting_period_id=NOVA_PERIOD_ID,
        raw_payload={"scenario": "correct_legal"},
        inline_lines=REPLACEMENT_LEGAL_LINES,
        journal_date=date(2026, 1, 22),
        currency="INR",
        explanation="Final audited legal advisory retainer with TDS",
    )
    assert j_corr.outcome == "POSTED"

    # -------------------------------------------------------------
    # 9. AWS Vendor Bill Settlement via Bank (2026-01-25)
    # -------------------------------------------------------------
    op_payout = nova_id("nova:op:payout")
    j_payout = await service.post_journal(
        operation_id=op_payout,
        proposal_id=nova_id("nova:prop:payout"),
        proposal_version=1,
        accounting_period_id=NOVA_PERIOD_ID,
        raw_payload={"scenario": "vendor_payout"},
        inline_lines=VENDOR_PAYOUT_LINES,
        journal_date=date(2026, 1, 25),
        currency="INR",
        explanation="Settlement of AWS Cloud hosting bill",
    )
    assert j_payout.outcome == "POSTED"

    # -------------------------------------------------------------
    # 10. Period Close Validation and Confirmation
    # -------------------------------------------------------------
    op_close = nova_id("nova:op:close")
    val_close = await service.validate_period_close(
        operation_id=op_close,
        accounting_period_id=NOVA_PERIOD_ID,
    )
    assert val_close.outcome == "VALIDATED"
    assert len(val_close.issues) == 0

    close_res = await service.close_period(
        operation_id=op_close,
        accounting_period_id=NOVA_PERIOD_ID,
        raw_payload={"period": str(NOVA_PERIOD_ID)},
    )
    assert close_res.outcome == "CLOSED"
    assert close_res.closed_at is not None

    # -------------------------------------------------------------
    # 11. Audited Financial Statements Verification
    # -------------------------------------------------------------
    now_as_of = datetime.now(UTC)

    # A. Trial Balance
    tb = await service.generate_statement(
        operation_id=nova_id("nova:op:tb_stmt"),
        accounting_period_id=NOVA_PERIOD_ID,
        statement_type="TRIAL_BALANCE",
        as_of=now_as_of,
        currency="INR",
    )
    tot_debits = next(
        line for line in tb.lines if line.account_reference == "TOTAL_DEBITS"
    ).amount.amount
    tot_credits = next(
        line for line in tb.lines if line.account_reference == "TOTAL_CREDITS"
    ).amount.amount
    assert tot_debits == EXPECTED_NOVA_FIGURES["total_debits"]
    assert tot_credits == EXPECTED_NOVA_FIGURES["total_credits"]
    assert tot_debits == tot_credits

    # B. Profit and Loss
    pl = await service.generate_statement(
        operation_id=nova_id("nova:op:pl_stmt"),
        accounting_period_id=NOVA_PERIOD_ID,
        statement_type="PROFIT_AND_LOSS",
        as_of=now_as_of,
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
    assert tot_rev == EXPECTED_NOVA_FIGURES["total_revenue"]
    assert tot_exp == EXPECTED_NOVA_FIGURES["total_expenses"]
    assert net_inc == EXPECTED_NOVA_FIGURES["net_income"]
    assert net_inc == tot_rev - tot_exp

    # C. Balance Sheet
    bs = await service.generate_statement(
        operation_id=nova_id("nova:op:bs_stmt"),
        accounting_period_id=NOVA_PERIOD_ID,
        statement_type="BALANCE_SHEET",
        as_of=now_as_of,
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

    assert tot_ast == EXPECTED_NOVA_FIGURES["total_assets"]
    assert tot_lia == EXPECTED_NOVA_FIGURES["total_liabilities"]
    assert tot_eq == EXPECTED_NOVA_FIGURES["total_equity"]
    assert tot_lia_eq == tot_lia + tot_eq
    assert tot_ast == tot_lia_eq
    # Balance sheet equation holds exactly to the penny:
    assert tot_ast - (tot_lia + tot_eq) == Decimal("0.00")
