"""Domain models and value objects for deterministic double-entry accounting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from ledgerai_contracts.v1.common import ProvenanceReference, ResourceReference


class AccountType(StrEnum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class NormalBalance(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


NORMAL_BALANCE_BY_TYPE: dict[AccountType, NormalBalance] = {
    AccountType.ASSET: NormalBalance.DEBIT,
    AccountType.LIABILITY: NormalBalance.CREDIT,
    AccountType.EQUITY: NormalBalance.CREDIT,
    AccountType.REVENUE: NormalBalance.CREDIT,
    AccountType.EXPENSE: NormalBalance.DEBIT,
}


class PeriodStatus(StrEnum):
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class Direction(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class PostingOutcome(StrEnum):
    POSTED = "POSTED"
    REJECTED = "REJECTED"
    IN_PROGRESS = "IN_PROGRESS"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"


class StatementType(StrEnum):
    TRIAL_BALANCE = "TRIAL_BALANCE"
    PROFIT_AND_LOSS = "PROFIT_AND_LOSS"
    BALANCE_SHEET = "BALANCE_SHEET"


class StatementStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class Account:
    account_code: str
    account_name: str
    account_type: AccountType
    normal_balance: NormalBalance
    currency: str
    is_active: bool = True
    description: str | None = None

    @classmethod
    def create(
        cls,
        code: str,
        name: str,
        account_type: AccountType,
        currency: str = "INR",
        normal_balance: NormalBalance | None = None,
        is_active: bool = True,
        description: str | None = None,
    ) -> Account:
        if normal_balance is None:
            normal_balance = NORMAL_BALANCE_BY_TYPE[account_type]
        return cls(
            account_code=code.strip(),
            account_name=name.strip(),
            account_type=account_type,
            normal_balance=normal_balance,
            currency=currency.strip().upper(),
            is_active=is_active,
            description=description,
        )


@dataclass(frozen=True, slots=True)
class DomainJournalLine:
    line_id: UUID
    account_reference: str
    direction: Direction
    amount: Decimal
    currency: str
    description: str | None = None
    source_evidence: list[ProvenanceReference] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DomainJournal:
    journal_id: UUID
    operation_id: UUID
    proposal_id: UUID
    proposal_version: int
    accounting_period_id: UUID
    journal_date: date
    currency: str
    explanation: str
    lines: list[DomainJournalLine]
    posted_at: datetime
    reversal_of_journal_id: UUID | None = None
    is_reversed: bool = False
    correlation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DomainStatementLine:
    line_id: str
    account_reference: str
    label: str
    amount: Decimal
    currency: str
    ledger_references: list[ResourceReference] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DomainStatement:
    snapshot_id: UUID
    accounting_period_id: UUID
    statement_type: StatementType
    currency: str
    as_of: datetime
    status: StatementStatus
    lines: list[DomainStatementLine]
