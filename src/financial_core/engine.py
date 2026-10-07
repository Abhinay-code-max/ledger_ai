"""Serialized in-memory reference engine; PostgreSQL adapter is a later phase."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from threading import RLock
from typing import Literal
from uuid import UUID, uuid4

from financial_core.money import AccountingError, decimal_amount, minor_units
from ledgerai_contracts.v1.approvals import ApprovalDecision
from ledgerai_contracts.v1.journals import JournalProposal
from ledgerai_contracts.v1.tenancy import EntityTenantContext

AccountKind = Literal["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"]
ContextKey = tuple[UUID, UUID, UUID]


def context_key(context: EntityTenantContext) -> ContextKey:
    return context.tenant_id, context.organization_id, context.legal_entity_id


def snapshot(model: JournalProposal | ApprovalDecision) -> str:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    kind: AccountKind
    active: bool = True

    def __post_init__(self) -> None:
        if (
            self.code != self.code.strip()
            or not self.code.strip()
            or not self.name.strip()
            or self.kind not in ("ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE")
        ):
            raise AccountingError("INVALID_ACCOUNT")


@dataclass(frozen=True)
class JournalLine:
    line_id: UUID
    account: str
    direction: Literal["DEBIT", "CREDIT"]
    units: int
    description: str | None
    evidence_json: tuple[str, ...]


@dataclass(frozen=True)
class JournalEntry:
    entry_id: UUID
    context: ContextKey
    journal_date: date
    currency: str
    lines: tuple[JournalLine, ...]
    proposal_id: UUID
    proposal_version: int
    approval_id: UUID
    source_json: str
    approval_json: str
    reversal_of: UUID | None = None
    reversal_reason: str | None = None


@dataclass(frozen=True)
class TrialBalanceRow:
    account: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class ProfitAndLoss:
    currency: str
    start: date
    end: date
    revenue: Decimal
    expenses: Decimal
    net_income: Decimal


@dataclass(frozen=True)
class BalanceSheet:
    currency: str
    as_of: date
    assets: Decimal
    liabilities: Decimal
    equity: Decimal
    retained_earnings: Decimal


@dataclass(frozen=True)
class PeriodClose:
    start: date
    end: date
    currency: str
    trial_balance: tuple[TrialBalanceRow, ...]
    profit_and_loss: ProfitAndLoss
    balance_sheet: BalanceSheet


class FinancialEngine:
    """One authenticated entity per engine; caller supplies trusted authorization context.

    The lock serializes operations within this instance only. State is not durable.
    Currency scales are explicit configuration, not an inferred ISO currency registry.
    """

    def __init__(
        self,
        context: EntityTenantContext,
        accounts: Iterable[Account],
        currency_scales: Mapping[str, int],
    ) -> None:
        self.context = context_key(context)
        self._accounts: dict[str, Account] = {}
        for account in accounts:
            if account.code in self._accounts:
                raise AccountingError("DUPLICATE_ACCOUNT")
            self._accounts[account.code] = account
        self._scales = dict(currency_scales)
        for currency, scale in self._scales.items():
            if (
                len(currency) != 3
                or not currency.isascii()
                or not currency.isalpha()
                or not currency.isupper()
            ):
                raise AccountingError("UNSUPPORTED_CURRENCY")
            minor_units("1", scale)
        self._entries: dict[UUID, JournalEntry] = {}
        self._posted: dict[UUID, tuple[int, str, UUID]] = {}
        self._reversed: dict[UUID, UUID] = {}
        self._closed: list[tuple[date, date]] = []
        self._lock = RLock()

    def _scale(self, currency: str) -> int:
        if currency not in self._scales:
            raise AccountingError("UNSUPPORTED_CURRENCY")
        return self._scales[currency]

    def _open(self, journal_date: date) -> None:
        if any(journal_date <= end for _, end in self._closed):
            raise AccountingError("PERIOD_CLOSED")

    def validate_proposal(self, proposal: JournalProposal) -> tuple[JournalLine, ...]:
        with self._lock:
            # Revalidate even model_construct/model_copy inputs before trusting invariants.
            proposal = JournalProposal.model_validate_json(snapshot(proposal))
            if context_key(proposal.tenant_context) != self.context:
                raise AccountingError("TENANT_MISMATCH")
            self._open(proposal.proposed_journal_date)
            scale = self._scale(proposal.currency)
            result: list[JournalLine] = []
            seen: set[UUID] = set()
            for line in proposal.lines:
                if line.line_id in seen:
                    raise AccountingError("DUPLICATE_LINE")
                seen.add(line.line_id)
                account = self._accounts.get(line.account_reference)
                if account is None or not account.active:
                    raise AccountingError("ACCOUNT_UNAVAILABLE")
                if line.amount.currency != proposal.currency:
                    raise AccountingError("CURRENCY_MISMATCH")
                evidence = tuple(item.model_dump_json() for item in line.source_evidence)
                if not all(
                    item.source_document_id or item.human_correction_id or item.evidence_hash
                    for item in line.source_evidence
                ):
                    raise AccountingError("EVIDENCE_UNRESOLVABLE")
                result.append(
                    JournalLine(
                        line.line_id,
                        line.account_reference,
                        line.direction,
                        minor_units(line.amount.amount, scale),
                        line.description,
                        evidence,
                    )
                )
            if not all(
                item.source_document_id or item.human_correction_id or item.evidence_hash
                for item in proposal.source_evidence
            ):
                raise AccountingError("EVIDENCE_UNRESOLVABLE")
            if (
                sum(line.units if line.direction == "DEBIT" else -line.units for line in result)
                != 0
            ):
                raise AccountingError("UNBALANCED_JOURNAL")
            return tuple(result)

    def _approval(self, proposal: JournalProposal, approval: ApprovalDecision) -> None:
        resource = approval.reviewed_resource
        if context_key(approval.tenant_context) != self.context:
            raise AccountingError("TENANT_MISMATCH")
        if (
            resource.resource_type != "journal_proposal"
            or resource.resource_id != proposal.proposal_id
            or resource.resource_version != str(proposal.proposal_version)
        ):
            raise AccountingError("APPROVAL_VERSION_MISMATCH")
        if (
            approval.action != "APPROVE"
            or approval.actor.actor_type != "HUMAN"
            or not approval.separation_of_duties_checked
        ):
            raise AccountingError("APPROVAL_REQUIRED")
        reference = proposal.approval_decision
        if reference is not None and (
            reference.resource_type != "approval_decision"
            or reference.resource_id != approval.decision_id
        ):
            raise AccountingError("APPROVAL_REFERENCE_MISMATCH")

    def post(self, proposal: JournalProposal, approval: ApprovalDecision) -> JournalEntry:
        with self._lock:
            proposal = JournalProposal.model_validate_json(snapshot(proposal))
            approval = ApprovalDecision.model_validate_json(snapshot(approval))
            self._approval(proposal, approval)
            source, decision = snapshot(proposal), snapshot(approval)
            digest = hashlib.sha256((source + decision).encode()).hexdigest()
            prior = self._posted.get(proposal.proposal_id)
            if prior is not None:
                if prior[:2] != (proposal.proposal_version, digest):
                    raise AccountingError("POSTING_CONFLICT")
                return self._entries[prior[2]]
            lines = self.validate_proposal(proposal)
            entry = JournalEntry(
                uuid4(),
                self.context,
                proposal.proposed_journal_date,
                proposal.currency,
                lines,
                proposal.proposal_id,
                proposal.proposal_version,
                approval.decision_id,
                source,
                decision,
            )
            self._entries[entry.entry_id] = entry
            self._posted[proposal.proposal_id] = (proposal.proposal_version, digest, entry.entry_id)
            return entry

    def reverse(self, entry_id: UUID, reversal_date: date, reason: str) -> JournalEntry:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                raise AccountingError("ENTRY_NOT_FOUND")
            if entry.reversal_of is not None:
                raise AccountingError("REVERSAL_OF_REVERSAL")
            if not reason.strip() or reversal_date < entry.journal_date:
                raise AccountingError("INVALID_REVERSAL")
            prior = self._reversed.get(entry_id)
            if prior is not None:
                reversal = self._entries[prior]
                if (reversal.journal_date, reversal.reversal_reason) != (reversal_date, reason):
                    raise AccountingError("REVERSAL_CONFLICT")
                return reversal
            self._open(reversal_date)
            lines = tuple(
                JournalLine(
                    uuid4(),
                    line.account,
                    "CREDIT" if line.direction == "DEBIT" else "DEBIT",
                    line.units,
                    line.description,
                    line.evidence_json,
                )
                for line in entry.lines
            )
            reversal = JournalEntry(
                uuid4(),
                self.context,
                reversal_date,
                entry.currency,
                lines,
                entry.proposal_id,
                entry.proposal_version,
                entry.approval_id,
                entry.source_json,
                entry.approval_json,
                entry.entry_id,
                reason,
            )
            self._entries[reversal.entry_id] = reversal
            self._reversed[entry_id] = reversal.entry_id
            return reversal

    @staticmethod
    def _range(start: date, end: date) -> None:
        if start > end:
            raise AccountingError("INVALID_DATE_RANGE")

    def general_ledger(
        self,
        currency: str,
        start: date = date.min,
        end: date = date.max,
    ) -> tuple[JournalEntry, ...]:
        with self._lock:
            self._scale(currency)
            self._range(start, end)
            return tuple(
                sorted(
                    (
                        entry
                        for entry in self._entries.values()
                        if entry.currency == currency and start <= entry.journal_date <= end
                    ),
                    key=lambda entry: (entry.journal_date, str(entry.entry_id)),
                )
            )

    def _balances(self, currency: str, start: date, end: date) -> dict[str, int]:
        balances = dict.fromkeys(self._accounts, 0)
        for entry in self.general_ledger(currency, start, end):
            for line in entry.lines:
                balances[line.account] += line.units if line.direction == "DEBIT" else -line.units
        return balances

    def account_balance(self, account: str, currency: str, as_of: date) -> Decimal:
        with self._lock:
            if account not in self._accounts:
                raise AccountingError("ACCOUNT_UNAVAILABLE")
            units = self._balances(currency, date.min, as_of)[account]
            return decimal_amount(units, self._scale(currency))

    def trial_balance(self, currency: str, as_of: date) -> tuple[TrialBalanceRow, ...]:
        with self._lock:
            scale = self._scale(currency)
            balances = self._balances(currency, date.min, as_of)
            return tuple(
                TrialBalanceRow(
                    code,
                    decimal_amount(max(units, 0), scale),
                    decimal_amount(max(-units, 0), scale),
                )
                for code, units in sorted(balances.items())
            )

    def profit_and_loss(self, currency: str, start: date, end: date) -> ProfitAndLoss:
        with self._lock:
            balances = self._balances(currency, start, end)
            revenue = -sum(
                value for code, value in balances.items() if self._accounts[code].kind == "REVENUE"
            )
            expenses = sum(
                value for code, value in balances.items() if self._accounts[code].kind == "EXPENSE"
            )
            scale = self._scale(currency)
            return ProfitAndLoss(
                currency,
                start,
                end,
                decimal_amount(revenue, scale),
                decimal_amount(expenses, scale),
                decimal_amount(revenue - expenses, scale),
            )

    def balance_sheet(self, currency: str, as_of: date) -> BalanceSheet:
        with self._lock:
            balances = self._balances(currency, date.min, as_of)
            totals = {
                kind: sum(
                    value for code, value in balances.items() if self._accounts[code].kind == kind
                )
                for kind in ("ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE")
            }
            scale = self._scale(currency)
            earnings = -totals["REVENUE"] - totals["EXPENSE"]
            return BalanceSheet(
                currency,
                as_of,
                decimal_amount(totals["ASSET"], scale),
                decimal_amount(-totals["LIABILITY"], scale),
                decimal_amount(-totals["EQUITY"] + earnings, scale),
                decimal_amount(earnings, scale),
            )

    def close_period(self, start: date, end: date) -> tuple[PeriodClose, ...]:
        with self._lock:
            self._range(start, end)
            if (start, end) in self._closed:
                return self._close_results(start, end)
            if any(
                start <= existing_end and existing_start <= end
                for existing_start, existing_end in self._closed
            ):
                raise AccountingError("PERIOD_OVERLAP")
            results = self._close_results(start, end)
            self._closed.append((start, end))
            return results

    def _close_results(self, start: date, end: date) -> tuple[PeriodClose, ...]:
        return tuple(
            PeriodClose(
                start,
                end,
                currency,
                self.trial_balance(currency, end),
                self.profit_and_loss(currency, start, end),
                self.balance_sheet(currency, end),
            )
            for currency in sorted(self._scales)
        )
