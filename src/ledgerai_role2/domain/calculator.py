"""Deterministic financial statement calculators with full provenance tracing."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from ledgerai_contracts.v1.common import ResourceReference
from ledgerai_role2.domain.models import (
    Account,
    AccountType,
    Direction,
    DomainJournal,
    DomainStatement,
    DomainStatementLine,
    NormalBalance,
    StatementStatus,
    StatementType,
)


def calculate_trial_balance(
    accounts: Mapping[str, Account],
    journals: list[DomainJournal],
    *,
    accounting_period_id: UUID,
    as_of: datetime,
    currency: str,
    snapshot_id: UUID | None = None,
) -> DomainStatement:
    """Generate a balanced Trial Balance statement with provenance references."""
    debits_by_account: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    credits_by_account: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    journal_refs_by_account: dict[str, set[tuple[str, UUID, str]]] = defaultdict(set)

    for journal in journals:
        j_ref = ("posted_journal", journal.journal_id, "1")
        for line in journal.lines:
            acc = line.account_reference
            journal_refs_by_account[acc].add(j_ref)
            if line.direction == Direction.DEBIT:
                debits_by_account[acc] += line.amount
            else:
                credits_by_account[acc] += line.amount

    all_accounts = sorted(set(accounts.keys()) | set(debits_by_account.keys()))
    lines: list[DomainStatementLine] = []

    total_debits = Decimal("0")
    total_credits = Decimal("0")

    for code in all_accounts:
        debit_amt = debits_by_account[code]
        credit_amt = credits_by_account[code]

        if debit_amt == Decimal("0") and credit_amt == Decimal("0"):
            continue

        account = accounts.get(code)
        label = account.account_name if account else f"Account {code}"
        normal_balance = account.normal_balance if account else NormalBalance.DEBIT

        if normal_balance == NormalBalance.DEBIT:
            net_balance = debit_amt - credit_amt
            if net_balance >= 0:
                total_debits += net_balance
            else:
                total_credits += abs(net_balance)
        else:
            net_balance = credit_amt - debit_amt
            if net_balance >= 0:
                total_credits += net_balance
            else:
                total_debits += abs(net_balance)

        refs = [
            ResourceReference(
                resource_type=r_type,
                resource_id=r_id,
                resource_version=r_ver,
            )
            for r_type, r_id, r_ver in sorted(journal_refs_by_account[code])
        ]

        lines.append(
            DomainStatementLine(
                line_id=f"tb-{code}",
                account_reference=code,
                label=label,
                amount=net_balance,
                currency=currency,
                ledger_references=refs,
            )
        )

    # Add summary total lines
    all_refs = [
        ResourceReference(
            resource_type=r_type,
            resource_id=r_id,
            resource_version=r_ver,
        )
        for r_type, r_id, r_ver in sorted(
            {ref for refs in journal_refs_by_account.values() for ref in refs}
        )
    ]
    lines.append(
        DomainStatementLine(
            line_id="tb-total-debits",
            account_reference="TOTAL_DEBITS",
            label="Total Debits",
            amount=total_debits,
            currency=currency,
            ledger_references=all_refs,
        )
    )
    lines.append(
        DomainStatementLine(
            line_id="tb-total-credits",
            account_reference="TOTAL_CREDITS",
            label="Total Credits",
            amount=total_credits,
            currency=currency,
            ledger_references=all_refs,
        )
    )

    return DomainStatement(
        snapshot_id=snapshot_id or uuid4(),
        accounting_period_id=accounting_period_id,
        statement_type=StatementType.TRIAL_BALANCE,
        currency=currency,
        as_of=as_of,
        status=StatementStatus.AVAILABLE,
        lines=lines,
    )


def calculate_profit_and_loss(
    accounts: Mapping[str, Account],
    journals: list[DomainJournal],
    *,
    accounting_period_id: UUID,
    as_of: datetime,
    currency: str,
    snapshot_id: UUID | None = None,
) -> tuple[DomainStatement, Decimal]:
    """Generate Profit and Loss (Income Statement) and return (statement, net_income)."""
    debits_by_account: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    credits_by_account: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    journal_refs_by_account: dict[str, set[tuple[str, UUID, str]]] = defaultdict(set)

    for journal in journals:
        j_ref = ("posted_journal", journal.journal_id, "1")
        for line in journal.lines:
            acc = line.account_reference
            journal_refs_by_account[acc].add(j_ref)
            if line.direction == Direction.DEBIT:
                debits_by_account[acc] += line.amount
            else:
                credits_by_account[acc] += line.amount

    revenue_lines: list[DomainStatementLine] = []
    expense_lines: list[DomainStatementLine] = []

    total_revenue = Decimal("0")
    total_expenses = Decimal("0")

    for code, account in sorted(accounts.items()):
        debit_amt = debits_by_account[code]
        credit_amt = credits_by_account[code]
        if debit_amt == Decimal("0") and credit_amt == Decimal("0"):
            continue

        refs = [
            ResourceReference(
                resource_type=r_type,
                resource_id=r_id,
                resource_version=r_ver,
            )
            for r_type, r_id, r_ver in sorted(journal_refs_by_account[code])
        ]

        if account.account_type == AccountType.REVENUE:
            # Credit increases revenue, Debit decreases
            net_rev = credit_amt - debit_amt
            total_revenue += net_rev
            revenue_lines.append(
                DomainStatementLine(
                    line_id=f"pl-rev-{code}",
                    account_reference=code,
                    label=account.account_name,
                    amount=net_rev,
                    currency=currency,
                    ledger_references=refs,
                )
            )
        elif account.account_type == AccountType.EXPENSE:
            # Debit increases expense, Credit decreases
            net_exp = debit_amt - credit_amt
            total_expenses += net_exp
            expense_lines.append(
                DomainStatementLine(
                    line_id=f"pl-exp-{code}",
                    account_reference=code,
                    label=account.account_name,
                    amount=net_exp,
                    currency=currency,
                    ledger_references=refs,
                )
            )

    net_income = total_revenue - total_expenses

    all_refs = [
        ResourceReference(
            resource_type=r_type,
            resource_id=r_id,
            resource_version=r_ver,
        )
        for r_type, r_id, r_ver in sorted(
            {ref for refs in journal_refs_by_account.values() for ref in refs}
        )
    ]

    summary_lines: list[DomainStatementLine] = [
        DomainStatementLine(
            line_id="pl-total-revenue",
            account_reference="TOTAL_REVENUE",
            label="Total Revenue",
            amount=total_revenue,
            currency=currency,
            ledger_references=all_refs,
        ),
        DomainStatementLine(
            line_id="pl-total-expenses",
            account_reference="TOTAL_EXPENSES",
            label="Total Expenses",
            amount=total_expenses,
            currency=currency,
            ledger_references=all_refs,
        ),
        DomainStatementLine(
            line_id="pl-net-income",
            account_reference="NET_INCOME",
            label="Net Income",
            amount=net_income,
            currency=currency,
            ledger_references=all_refs,
        ),
    ]

    statement = DomainStatement(
        snapshot_id=snapshot_id or uuid4(),
        accounting_period_id=accounting_period_id,
        statement_type=StatementType.PROFIT_AND_LOSS,
        currency=currency,
        as_of=as_of,
        status=StatementStatus.AVAILABLE,
        lines=revenue_lines + expense_lines + summary_lines,
    )
    return statement, net_income


def calculate_balance_sheet(
    accounts: Mapping[str, Account],
    journals: list[DomainJournal],
    net_income: Decimal,
    *,
    accounting_period_id: UUID,
    as_of: datetime,
    currency: str,
    snapshot_id: UUID | None = None,
) -> DomainStatement:
    """Generate Balance Sheet verifying Assets == Liabilities + Equity."""
    debits_by_account: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    credits_by_account: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    journal_refs_by_account: dict[str, set[tuple[str, UUID, str]]] = defaultdict(set)

    for journal in journals:
        j_ref = ("posted_journal", journal.journal_id, "1")
        for line in journal.lines:
            acc = line.account_reference
            journal_refs_by_account[acc].add(j_ref)
            if line.direction == Direction.DEBIT:
                debits_by_account[acc] += line.amount
            else:
                credits_by_account[acc] += line.amount

    asset_lines: list[DomainStatementLine] = []
    liability_lines: list[DomainStatementLine] = []
    equity_lines: list[DomainStatementLine] = []

    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    total_equity_direct = Decimal("0")

    for code, account in sorted(accounts.items()):
        debit_amt = debits_by_account[code]
        credit_amt = credits_by_account[code]
        if debit_amt == Decimal("0") and credit_amt == Decimal("0"):
            continue

        refs = [
            ResourceReference(
                resource_type=r_type,
                resource_id=r_id,
                resource_version=r_ver,
            )
            for r_type, r_id, r_ver in sorted(journal_refs_by_account[code])
        ]

        if account.account_type == AccountType.ASSET:
            net_asset = debit_amt - credit_amt
            total_assets += net_asset
            asset_lines.append(
                DomainStatementLine(
                    line_id=f"bs-ast-{code}",
                    account_reference=code,
                    label=account.account_name,
                    amount=net_asset,
                    currency=currency,
                    ledger_references=refs,
                )
            )
        elif account.account_type == AccountType.LIABILITY:
            net_liab = credit_amt - debit_amt
            total_liabilities += net_liab
            liability_lines.append(
                DomainStatementLine(
                    line_id=f"bs-lia-{code}",
                    account_reference=code,
                    label=account.account_name,
                    amount=net_liab,
                    currency=currency,
                    ledger_references=refs,
                )
            )
        elif account.account_type == AccountType.EQUITY:
            net_eq = credit_amt - debit_amt
            total_equity_direct += net_eq
            equity_lines.append(
                DomainStatementLine(
                    line_id=f"bs-eq-{code}",
                    account_reference=code,
                    label=account.account_name,
                    amount=net_eq,
                    currency=currency,
                    ledger_references=refs,
                )
            )

    all_refs = [
        ResourceReference(
            resource_type=r_type,
            resource_id=r_id,
            resource_version=r_ver,
        )
        for r_type, r_id, r_ver in sorted(
            {ref for refs in journal_refs_by_account.values() for ref in refs}
        )
    ]

    # Total Equity includes direct equity + current period Net Income
    total_equity = total_equity_direct + net_income

    equity_lines.append(
        DomainStatementLine(
            line_id="bs-current-period-earnings",
            account_reference="CURRENT_PERIOD_EARNINGS",
            label="Current Period Net Income (Retained Earnings)",
            amount=net_income,
            currency=currency,
            ledger_references=all_refs,
        )
    )

    summary_lines: list[DomainStatementLine] = [
        DomainStatementLine(
            line_id="bs-total-assets",
            account_reference="TOTAL_ASSETS",
            label="Total Assets",
            amount=total_assets,
            currency=currency,
            ledger_references=all_refs,
        ),
        DomainStatementLine(
            line_id="bs-total-liabilities",
            account_reference="TOTAL_LIABILITIES",
            label="Total Liabilities",
            amount=total_liabilities,
            currency=currency,
            ledger_references=all_refs,
        ),
        DomainStatementLine(
            line_id="bs-total-equity",
            account_reference="TOTAL_EQUITY",
            label="Total Equity",
            amount=total_equity,
            currency=currency,
            ledger_references=all_refs,
        ),
        DomainStatementLine(
            line_id="bs-total-liabilities-and-equity",
            account_reference="TOTAL_LIABILITIES_AND_EQUITY",
            label="Total Liabilities and Equity",
            amount=total_liabilities + total_equity,
            currency=currency,
            ledger_references=all_refs,
        ),
    ]

    return DomainStatement(
        snapshot_id=snapshot_id or uuid4(),
        accounting_period_id=accounting_period_id,
        statement_type=StatementType.BALANCE_SHEET,
        currency=currency,
        as_of=as_of,
        status=StatementStatus.AVAILABLE,
        lines=asset_lines + liability_lines + equity_lines + summary_lines,
    )
