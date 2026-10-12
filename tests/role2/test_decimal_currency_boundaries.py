"""Tests for Decimal precision, floating-point rejection, and ISO currency boundaries."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ledgerai_contracts.v1.common import Money, PositiveMoney, ProvenanceReference
from ledgerai_role2.domain.invariants import validate_journal_lines
from ledgerai_role2.domain.models import (
    Account,
    AccountType,
    Direction,
    DomainJournalLine,
    NormalBalance,
)

ACCOUNTS = {
    "1010": Account.create("1010", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT),
    "4010": Account.create("4010", "Revenue", AccountType.REVENUE, "INR", NormalBalance.CREDIT),
}


def test_money_rejects_binary_floats() -> None:
    with pytest.raises(ValidationError, match="decimal string"):
        Money(amount=125.50, currency="INR")  # type: ignore[arg-type]


def test_money_rejects_integer_without_string() -> None:
    with pytest.raises(ValidationError, match="decimal string"):
        Money(amount=100, currency="INR")  # type: ignore[arg-type]


def test_money_accepts_canonical_decimal_string() -> None:
    m = Money.model_validate({"amount": "125.50", "currency": "INR"})
    assert m.amount == Decimal("125.50")
    assert format(m.amount, "f") == "125.50"


def test_positive_money_rejects_zero_or_negative() -> None:
    with pytest.raises(ValidationError, match="greater than zero"):
        PositiveMoney.model_validate({"amount": "0.00", "currency": "INR"})

    with pytest.raises(ValidationError, match="greater than zero"):
        PositiveMoney.model_validate({"amount": "-50.00", "currency": "INR"})


DUMMY_EVIDENCE = [
    ProvenanceReference(
        source_document_id=uuid4(),
        document_version="1",
        evidence_hash="0" * 64,
    )
]


def test_currency_mismatch_between_lines_and_header_rejected() -> None:
    lines = [
        DomainJournalLine(
            line_id=uuid4(),
            account_reference="1010",
            direction=Direction.DEBIT,
            amount=Decimal("100.00"),
            currency="USD",  # mismatch with INR
            source_evidence=DUMMY_EVIDENCE,
        ),
        DomainJournalLine(
            line_id=uuid4(),
            account_reference="4010",
            direction=Direction.CREDIT,
            amount=Decimal("100.00"),
            currency="INR",
            source_evidence=DUMMY_EVIDENCE,
        ),
    ]
    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    assert any(i.code == "CURRENCY_MISMATCH" for i in issues)


def test_invalid_header_currency_rejected() -> None:
    lines = [
        DomainJournalLine(
            line_id=uuid4(),
            account_reference="1010",
            direction=Direction.DEBIT,
            amount=Decimal("100.00"),
            currency="US",
            source_evidence=DUMMY_EVIDENCE,
        ),
        DomainJournalLine(
            line_id=uuid4(),
            account_reference="4010",
            direction=Direction.CREDIT,
            amount=Decimal("100.00"),
            currency="US",
            source_evidence=DUMMY_EVIDENCE,
        ),
    ]
    issues = validate_journal_lines(lines, "US", ACCOUNTS)
    assert any(i.code == "INVALID_CURRENCY" for i in issues)


def test_exact_high_precision_decimals_balance() -> None:
    amt = Decimal("123456789.123456")
    lines = [
        DomainJournalLine(
            line_id=uuid4(),
            account_reference="1010",
            direction=Direction.DEBIT,
            amount=amt,
            currency="INR",
            source_evidence=DUMMY_EVIDENCE,
        ),
        DomainJournalLine(
            line_id=uuid4(),
            account_reference="4010",
            direction=Direction.CREDIT,
            amount=amt,
            currency="INR",
            source_evidence=DUMMY_EVIDENCE,
        ),
    ]
    issues = validate_journal_lines(lines, "INR", ACCOUNTS)
    assert len(issues) == 0
