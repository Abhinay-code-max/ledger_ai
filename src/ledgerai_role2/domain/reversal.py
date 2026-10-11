"""Deterministic reversal and correcting entry generation."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from ledgerai_role2.domain.models import (
    Direction,
    DomainJournal,
    DomainJournalLine,
)


def create_reversal_journal(
    original_journal: DomainJournal,
    *,
    reversal_operation_id: UUID,
    accounting_period_id: UUID,
    reversal_date: date,
    now: datetime,
    reason: str = "Correcting reversal entry",
    correlation_id: UUID | None = None,
) -> DomainJournal:
    """Create an exact reversing journal with inverted lines."""
    reversal_lines: list[DomainJournalLine] = []

    for line in original_journal.lines:
        inverted_direction = (
            Direction.CREDIT if line.direction == Direction.DEBIT else Direction.DEBIT
        )
        reversal_lines.append(
            DomainJournalLine(
                line_id=uuid4(),
                account_reference=line.account_reference,
                direction=inverted_direction,
                amount=line.amount,
                currency=line.currency,
                description=f"Reversal: {line.description or 'line'}",
                source_evidence=list(line.source_evidence),
            )
        )

    return DomainJournal(
        journal_id=uuid4(),
        operation_id=reversal_operation_id,
        proposal_id=original_journal.proposal_id,
        proposal_version=original_journal.proposal_version,
        accounting_period_id=accounting_period_id,
        journal_date=reversal_date,
        currency=original_journal.currency,
        explanation=f"Reversal of journal {original_journal.journal_id}: {reason}",
        lines=reversal_lines,
        posted_at=now,
        reversal_of_journal_id=original_journal.journal_id,
        is_reversed=False,
        correlation_id=correlation_id or original_journal.correlation_id,
    )
