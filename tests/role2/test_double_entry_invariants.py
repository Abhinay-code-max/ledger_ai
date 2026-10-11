"""Unit and property tests for double-entry invariants and balancing."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from ledgerai_contracts.v1.common import ProvenanceReference
from ledgerai_role2.domain.invariants import validate_journal_lines
from ledgerai_role2.domain.models import (
    Account,
    AccountType,
    Direction,
    DomainJournalLine,
    NormalBalance,
)

EVIDENCE = [
    ProvenanceReference(
        source_document_id=uuid4(),
        document_version="1",
        evidence_hash="b" * 64,
    )
]

ACCOUNTS = {
    "1010": Account.create("1010", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT),
    "2010": Account.create("2010", "Payable", AccountType.LIABILITY, "INR", NormalBalance.CREDIT),
    "4010": Account.create("4010", "Revenue", AccountType.REVENUE, "INR", NormalBalance.CREDIT),
    "5010": Account.create("5010", "Expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT),
}


def make_line(
    account: str,
    direction: Direction,
    amount: Decimal,
    currency: str = "INR",
    has_evidence: bool = True,
) -> DomainJournalLine:
    return DomainJournalLine(
        line_id=uuid4(),
        account_reference=account,
        direction=direction,
        amount=amount,
        currency=currency,
        source_evidence=EVIDENCE if has_evidence else [],
    )


def test_balanced_two_legged_journal_passes() -> None:
    lines = [
        make_line("1010", Direction.DEBIT, Decimal("500.00")),
        make_line("4010", Direction.CREDIT, Decimal("500.00")),
    ]
    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    assert len(issues) == 0


def test_unbalanced_journal_rejected() -> None:
    lines = [
        make_line("1010", Direction.DEBIT, Decimal("500.00")),
        make_line("4010", Direction.CREDIT, Decimal("499.99")),
    ]
    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    assert any(i.code == "UNBALANCED_JOURNAL" for i in issues)


def test_insufficient_lines_rejected() -> None:
    lines = [make_line("1010", Direction.DEBIT, Decimal("100.00"))]
    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    assert any(i.code == "INSUFFICIENT_LINES" for i in issues)


def test_missing_credit_direction_rejected() -> None:
    lines = [
        make_line("1010", Direction.DEBIT, Decimal("100.00")),
        make_line("5010", Direction.DEBIT, Decimal("100.00")),
    ]
    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    assert any(i.code == "MISSING_CREDIT_LINE" for i in issues)


def test_missing_debit_direction_rejected() -> None:
    lines = [
        make_line("2010", Direction.CREDIT, Decimal("100.00")),
        make_line("4010", Direction.CREDIT, Decimal("100.00")),
    ]
    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    assert any(i.code == "MISSING_DEBIT_LINE" for i in issues)


def test_zero_or_negative_amount_rejected() -> None:
    lines = [
        make_line("1010", Direction.DEBIT, Decimal("0.00")),
        make_line("4010", Direction.CREDIT, Decimal("0.00")),
    ]
    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    assert any(i.code == "NON_POSITIVE_AMOUNT" for i in issues)


def test_missing_evidence_chain_rejected() -> None:
    lines = [
        make_line("1010", Direction.DEBIT, Decimal("100.00"), has_evidence=False),
        make_line("4010", Direction.CREDIT, Decimal("100.00"), has_evidence=True),
    ]
    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    assert any(i.code == "MISSING_EVIDENCE_CHAIN" for i in issues)


def test_unknown_account_reference_rejected() -> None:
    lines = [
        make_line("9999", Direction.DEBIT, Decimal("100.00")),
        make_line("4010", Direction.CREDIT, Decimal("100.00")),
    ]
    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    assert any(i.code == "UNKNOWN_ACCOUNT" for i in issues)


@pytest.mark.parametrize(
    ("debits", "credits", "balanced"),
    [
        ([Decimal("100.00"), Decimal("50.00")], [Decimal("150.00")], True),
        ([Decimal("10.25"), Decimal("20.35")], [Decimal("15.00"), Decimal("15.60")], True),
        ([Decimal("10.25"), Decimal("20.35")], [Decimal("30.59")], False),
        ([Decimal("0.0001"), Decimal("0.0002")], [Decimal("0.0003")], True),
        ([Decimal("999999999.99")], [Decimal("999999999.99")], True),
    ],
)
def test_property_multi_leg_combinations(
    debits: list[Decimal], credits: list[Decimal], balanced: bool
) -> None:
    lines: list[DomainJournalLine] = []
    for d in debits:
        lines.append(make_line("1010", Direction.DEBIT, d))
    for c in credits:
        lines.append(make_line("4010", Direction.CREDIT, c))

    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    unbalanced_issues = [i for i in issues if i.code == "UNBALANCED_JOURNAL"]
    assert (len(unbalanced_issues) == 0) == balanced
