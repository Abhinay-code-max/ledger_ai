"""Deterministic validation of non-negotiable double-entry accounting invariants."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from ledgerai_contracts.v1.common import ValidationIssue
from ledgerai_role2.domain.models import (
    Account,
    Direction,
    DomainJournalLine,
    PeriodStatus,
)

CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


def validate_journal_lines(
    lines: list[DomainJournalLine],
    expected_currency: str,
    accounts: Mapping[str, Account] | None = None,
) -> list[ValidationIssue]:
    """Validate double-entry invariants, currency consistency, and accounts."""
    issues: list[ValidationIssue] = []

    if not CURRENCY_PATTERN.match(expected_currency):
        issues.append(
            ValidationIssue(
                code="INVALID_CURRENCY",
                message=f"Journal currency '{expected_currency}' is not a valid 3-letter ISO code",
                field="currency",
                severity="ERROR",
            )
        )

    if len(lines) < 2:
        issues.append(
            ValidationIssue(
                code="INSUFFICIENT_LINES",
                message=f"Journal requires at least 2 lines; got {len(lines)}",
                field="lines",
                severity="ERROR",
            )
        )

    debit_count = 0
    credit_count = 0
    debit_total = Decimal("0")
    credit_total = Decimal("0")

    for idx, line in enumerate(lines):
        prefix = f"lines[{idx}]"

        # Check currency match
        if line.currency != expected_currency:
            issues.append(
                ValidationIssue(
                    code="CURRENCY_MISMATCH",
                    message=(
                        f"Line currency '{line.currency}' does not match "
                        f"journal currency '{expected_currency}'"
                    ),
                    field=f"{prefix}.currency",
                    severity="ERROR",
                )
            )

        # Check strictly positive amount
        if not isinstance(line.amount, Decimal):
            issues.append(
                ValidationIssue(
                    code="INVALID_AMOUNT_TYPE",
                    message="Amount must be a fixed-precision Decimal, floats are prohibited",
                    field=f"{prefix}.amount",
                    severity="ERROR",
                )
            )
        elif line.amount <= Decimal("0"):
            issues.append(
                ValidationIssue(
                    code="NON_POSITIVE_AMOUNT",
                    message=f"Line amount must be strictly greater than zero; got {line.amount}",
                    field=f"{prefix}.amount",
                    severity="ERROR",
                )
            )
        else:
            if line.direction == Direction.DEBIT:
                debit_count += 1
                debit_total += line.amount
            elif line.direction == Direction.CREDIT:
                credit_count += 1
                credit_total += line.amount
            else:
                issues.append(
                    ValidationIssue(
                        code="INVALID_DIRECTION",
                        message=f"Line direction must be DEBIT or CREDIT; got '{line.direction}'",
                        field=f"{prefix}.direction",
                        severity="ERROR",
                    )
                )

        # Check evidence chain
        if not line.source_evidence:
            issues.append(
                ValidationIssue(
                    code="MISSING_EVIDENCE_CHAIN",
                    message="Every ledger line must reference its source evidence chain",
                    field=f"{prefix}.source_evidence",
                    severity="ERROR",
                )
            )

        # Check Chart of Accounts if provided
        if accounts is not None:
            account = accounts.get(line.account_reference)
            if account is None:
                issues.append(
                    ValidationIssue(
                        code="UNKNOWN_ACCOUNT",
                        message=(
                            f"Account reference '{line.account_reference}' does not exist in chart"
                        ),
                        field=f"{prefix}.account_reference",
                        severity="ERROR",
                    )
                )
            elif not account.is_active:
                issues.append(
                    ValidationIssue(
                        code="INACTIVE_ACCOUNT",
                        message=f"Account '{line.account_reference}' is inactive",
                        field=f"{prefix}.account_reference",
                        severity="ERROR",
                    )
                )

    if debit_count == 0:
        issues.append(
            ValidationIssue(
                code="MISSING_DEBIT_LINE",
                message="Journal must contain at least one DEBIT line",
                field="lines",
                severity="ERROR",
            )
        )
    if credit_count == 0:
        issues.append(
            ValidationIssue(
                code="MISSING_CREDIT_LINE",
                message="Journal must contain at least one CREDIT line",
                field="lines",
                severity="ERROR",
            )
        )

    # Double-entry exact equality
    if debit_total != credit_total:
        diff = abs(debit_total - credit_total)
        issues.append(
            ValidationIssue(
                code="UNBALANCED_JOURNAL",
                message=(
                    f"Debit total ({debit_total}) does not equal credit total ({credit_total}); "
                    f"difference is {diff}"
                ),
                field="lines",
                severity="ERROR",
            )
        )

    return issues


def validate_period_for_posting(
    period_start: date,
    period_end: date,
    period_status: PeriodStatus,
    journal_date: date,
) -> list[ValidationIssue]:
    """Validate that the period is open and spans the journal date."""
    issues: list[ValidationIssue] = []

    if period_status != PeriodStatus.OPEN:
        issues.append(
            ValidationIssue(
                code="PERIOD_NOT_OPEN",
                message=f"Accounting period is {period_status}; closed periods reject postings",
                field="accounting_period_id",
                severity="ERROR",
            )
        )

    if not (period_start <= journal_date <= period_end):
        issues.append(
            ValidationIssue(
                code="POSTING_DATE_OUTSIDE_PERIOD",
                message=(
                    f"Journal date {journal_date} is outside the accounting period boundary "
                    f"[{period_start} to {period_end}]"
                ),
                field="journal_date",
                severity="ERROR",
            )
        )

    return issues
