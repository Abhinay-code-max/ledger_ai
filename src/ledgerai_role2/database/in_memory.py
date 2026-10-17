"""Deterministic in-memory repository implementation for unit testing and fast evaluation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from ledgerai_contracts.v1.common import (
    ProvenanceReference,
    ValidationIssue,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role2.database.models import (
    Role2Account,
    Role2AccountingPeriod,
    Role2JournalLine,
    Role2PeriodCloseOperation,
    Role2PostedJournal,
    Role2PostingOperation,
    Role2ProposalRecord,
    Role2StatementLine,
    Role2StatementSnapshot,
)
from ledgerai_role2.domain.models import (
    Account,
    AccountType,
    DomainJournal,
    DomainJournalLine,
    DomainStatement,
    NormalBalance,
    PeriodStatus,
)
from ledgerai_role2.domain.state_machine import PostingState

STANDARD_ACCOUNTS: dict[str, Account] = {
    "1100": Account.create("1100", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT),
    "2100": Account.create(
        "2100", "Trade payables", AccountType.LIABILITY, "INR", NormalBalance.CREDIT
    ),
    "6100": Account.create(
        "6100", "Office expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT
    ),
}


class InMemoryRole2Repository:
    def __init__(
        self, tenant_context: EntityTenantContext, shared_store: dict[str, Any] | None = None
    ) -> None:
        self.context = tenant_context
        self._store = (
            shared_store
            if shared_store is not None
            else {
                "accounts": {},
                "periods": {},
                "proposals": {},
                "posting_ops": {},
                "close_ops": {},
                "journals": {},
                "journal_lines": {},
                "snapshots": {},
                "statement_lines": {},
            }
        )

    @property
    def tenant_id(self) -> UUID:
        return self.context.tenant_id

    @property
    def organization_id(self) -> UUID:
        return self.context.organization_id

    @property
    def legal_entity_id(self) -> UUID:
        return self.context.legal_entity_id

    def _scope_key(self, key: Any) -> tuple[UUID, UUID, UUID, Any]:
        return (self.tenant_id, self.organization_id, self.legal_entity_id, key)

    # ---------------------------------------------------------
    # Chart of Accounts
    # ---------------------------------------------------------
    async def get_account(self, account_code: str) -> Role2Account | None:
        key = self._scope_key(account_code)
        acc = cast(Role2Account | None, self._store["accounts"].get(key))
        if acc is None and account_code in STANDARD_ACCOUNTS:
            acc = await self.save_account(STANDARD_ACCOUNTS[account_code])
        return acc

    async def list_accounts(self) -> Sequence[Role2Account]:
        scope_prefix = (self.tenant_id, self.organization_id, self.legal_entity_id)
        accounts = [acc for k, acc in self._store["accounts"].items() if k[:3] == scope_prefix]
        if not accounts:
            for acc in STANDARD_ACCOUNTS.values():
                await self.save_account(acc)
            accounts = [acc for k, acc in self._store["accounts"].items() if k[:3] == scope_prefix]
        return accounts

    async def save_account(self, account: Account) -> Role2Account:
        key = self._scope_key(account.account_code)
        existing = self._store["accounts"].get(key)
        if existing is not None:
            existing.account_name = account.account_name
            existing.account_type = account.account_type
            existing.normal_balance = account.normal_balance
            existing.currency = account.currency
            existing.is_active = account.is_active
            existing.description = account.description
            return cast(Role2Account, existing)

        row = Role2Account(
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            account_code=account.account_code,
            account_name=account.account_name,
            account_type=account.account_type,
            normal_balance=account.normal_balance,
            currency=account.currency,
            is_active=account.is_active,
            description=account.description,
        )
        self._store["accounts"][key] = row
        return row

    # ---------------------------------------------------------
    # Accounting Periods
    # ---------------------------------------------------------
    async def get_period(
        self, period_id: UUID, *, lock: bool = False
    ) -> Role2AccountingPeriod | None:
        key = self._scope_key(period_id)
        period = cast(Role2AccountingPeriod | None, self._store["periods"].get(key))
        if period is None:
            period = await self.save_period(
                period_id=period_id,
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
                state=PeriodStatus.OPEN,
            )
        return period

    async def save_period(
        self,
        *,
        period_id: UUID,
        period_start: date,
        period_end: date,
        state: PeriodStatus = PeriodStatus.OPEN,
    ) -> Role2AccountingPeriod:
        key = self._scope_key(period_id)
        existing = self._store["periods"].get(key)
        if existing is not None:
            return cast(Role2AccountingPeriod, existing)

        row = Role2AccountingPeriod(
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            id=period_id,
            period_start=period_start,
            period_end=period_end,
            state=state,
        )
        self._store["periods"][key] = row
        return row

    # ---------------------------------------------------------
    # Proposals Registry
    # ---------------------------------------------------------
    async def get_proposal(self, proposal_id: UUID, version: int) -> Role2ProposalRecord | None:
        key = self._scope_key((proposal_id, version))
        prop = cast(Role2ProposalRecord | None, self._store["proposals"].get(key))
        if prop is None:
            prop = await self.save_proposal_record(
                proposal_id=proposal_id,
                proposal_version=version,
                proposed_journal_date=date(2026, 9, 15),
                currency="INR",
                explanation="Synthetic NOVA invoice proposal",
                lines_payload=[
                    {
                        "account_reference": "6100",
                        "direction": "DEBIT",
                        "amount": {"amount": "1250.00", "currency": "INR"},
                        "description": "Office expense debit",
                        "source_evidence": [
                            {
                                "source_document_id": str(proposal_id),
                                "document_version": "1",
                                "source_field": "invoice",
                                "evidence_hash": "a" * 64,
                            }
                        ],
                    },
                    {
                        "account_reference": "1100",
                        "direction": "CREDIT",
                        "amount": {"amount": "1250.00", "currency": "INR"},
                        "description": "Cash credit",
                        "source_evidence": [
                            {
                                "source_document_id": str(proposal_id),
                                "document_version": "1",
                                "source_field": "invoice",
                                "evidence_hash": "a" * 64,
                            }
                        ],
                    },
                ],
                source_evidence=[
                    {
                        "source_document_id": str(proposal_id),
                        "document_version": "1",
                        "source_field": "invoice",
                        "evidence_hash": "a" * 64,
                    }
                ],
            )
        return prop

    async def save_proposal_record(
        self,
        *,
        proposal_id: UUID,
        proposal_version: int,
        proposed_journal_date: date,
        currency: str,
        explanation: str,
        lines_payload: list[dict[str, Any]],
        source_evidence: list[dict[str, Any]],
        approval_decision: dict[str, Any] | None = None,
    ) -> Role2ProposalRecord:
        key = self._scope_key((proposal_id, proposal_version))
        existing = self._store["proposals"].get(key)
        if existing is not None:
            return cast(Role2ProposalRecord, existing)

        row = Role2ProposalRecord(
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            proposed_journal_date=proposed_journal_date,
            currency=currency,
            explanation=explanation,
            lines_payload=lines_payload,
            source_evidence=source_evidence,
            approval_decision=approval_decision,
        )
        self._store["proposals"][key] = row
        return row

    # ---------------------------------------------------------
    # Posting Operations
    # ---------------------------------------------------------
    async def get_posting_operation(
        self, operation_id: UUID, *, lock: bool = False
    ) -> Role2PostingOperation | None:
        key = self._scope_key(operation_id)
        return cast(Role2PostingOperation | None, self._store["posting_ops"].get(key))

    async def create_posting_operation(
        self,
        *,
        operation_id: UUID,
        proposal_id: UUID,
        proposal_version: int,
        accounting_period_id: UUID,
        request_hash: str,
        state: PostingState,
        issues: list[ValidationIssue] | None = None,
    ) -> Role2PostingOperation:
        key = self._scope_key(operation_id)
        row = Role2PostingOperation(
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            operation_id=operation_id,
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            accounting_period_id=accounting_period_id,
            request_hash=request_hash,
            state=state,
            issues=[issue.model_dump(mode="json") for issue in (issues or [])],
        )
        self._store["posting_ops"][key] = row
        return row

    # ---------------------------------------------------------
    # Posted Journals & Ledger Lines
    # ---------------------------------------------------------
    async def get_journal(self, journal_id: UUID) -> Role2PostedJournal | None:
        key = self._scope_key(journal_id)
        return cast(Role2PostedJournal | None, self._store["journals"].get(key))

    async def get_journal_by_operation(self, operation_id: UUID) -> Role2PostedJournal | None:
        scope_prefix = (self.tenant_id, self.organization_id, self.legal_entity_id)
        for k, j in self._store["journals"].items():
            if k[:3] == scope_prefix and j.operation_id == operation_id:
                return cast(Role2PostedJournal, j)
        return None

    async def save_journal_with_lines(self, journal: DomainJournal) -> Role2PostedJournal:
        key = self._scope_key(journal.journal_id)
        journal_row = Role2PostedJournal(
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            id=journal.journal_id,
            operation_id=journal.operation_id,
            proposal_id=journal.proposal_id,
            proposal_version=journal.proposal_version,
            accounting_period_id=journal.accounting_period_id,
            journal_date=journal.journal_date,
            currency=journal.currency,
            explanation=journal.explanation,
            reversal_of_journal_id=journal.reversal_of_journal_id,
            is_reversed=journal.is_reversed,
            posted_at=journal.posted_at,
            correlation_id=journal.correlation_id or journal.journal_id,
        )
        self._store["journals"][key] = journal_row

        stored_lines = []
        for idx, line in enumerate(journal.lines, start=1):
            line_row = Role2JournalLine(
                tenant_id=self.tenant_id,
                organization_id=self.organization_id,
                legal_entity_id=self.legal_entity_id,
                id=line.line_id,
                journal_id=journal.journal_id,
                line_number=idx,
                account_reference=line.account_reference,
                direction=line.direction,
                amount=line.amount,
                currency=line.currency,
                description=line.description,
                source_evidence=[e.model_dump(mode="json") for e in line.source_evidence],
            )
            stored_lines.append(line_row)
        self._store["journal_lines"][journal.journal_id] = stored_lines
        return journal_row

    async def mark_journal_reversed(self, journal_id: UUID) -> None:
        journal = await self.get_journal(journal_id)
        if journal is not None:
            journal.is_reversed = True

    async def list_domain_journals_for_period(self, period_id: UUID) -> list[DomainJournal]:
        scope_prefix = (self.tenant_id, self.organization_id, self.legal_entity_id)
        results: list[DomainJournal] = []

        matching_journals = [
            j
            for k, j in self._store["journals"].items()
            if k[:3] == scope_prefix and j.accounting_period_id == period_id
        ]
        matching_journals.sort(key=lambda j: (j.journal_date, j.posted_at))

        for j in matching_journals:
            raw_lines = self._store["journal_lines"].get(j.id, [])
            domain_lines = [
                DomainJournalLine(
                    line_id=line.id,
                    account_reference=line.account_reference,
                    direction=line.direction,
                    amount=Decimal(str(line.amount)),
                    currency=line.currency,
                    description=line.description,
                    source_evidence=[
                        ProvenanceReference.model_validate(e) for e in line.source_evidence
                    ],
                )
                for line in raw_lines
            ]
            results.append(
                DomainJournal(
                    journal_id=j.id,
                    operation_id=j.operation_id,
                    proposal_id=j.proposal_id,
                    proposal_version=j.proposal_version,
                    accounting_period_id=j.accounting_period_id,
                    journal_date=j.journal_date,
                    currency=j.currency,
                    explanation=j.explanation,
                    lines=domain_lines,
                    posted_at=j.posted_at,
                    reversal_of_journal_id=j.reversal_of_journal_id,
                    is_reversed=j.is_reversed,
                    correlation_id=j.correlation_id,
                )
            )
        return results

    # ---------------------------------------------------------
    # Period Close Operations
    # ---------------------------------------------------------
    async def get_close_operation(self, operation_id: UUID) -> Role2PeriodCloseOperation | None:
        key = self._scope_key(operation_id)
        return cast(Role2PeriodCloseOperation | None, self._store["close_ops"].get(key))

    async def create_close_operation(
        self,
        *,
        operation_id: UUID,
        accounting_period_id: UUID,
        state: str,
        request_hash: str,
        closed_at: datetime | None = None,
        issues: list[ValidationIssue] | None = None,
    ) -> Role2PeriodCloseOperation:
        key = self._scope_key(operation_id)
        row = Role2PeriodCloseOperation(
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            operation_id=operation_id,
            accounting_period_id=accounting_period_id,
            state=state,
            request_hash=request_hash,
            closed_at=closed_at,
            issues=[issue.model_dump(mode="json") for issue in (issues or [])],
        )
        self._store["close_ops"][key] = row
        return row

    # ---------------------------------------------------------
    # Statement Snapshots & Lines
    # ---------------------------------------------------------
    async def get_statement_snapshot(self, snapshot_id: UUID) -> Role2StatementSnapshot | None:
        key = self._scope_key(snapshot_id)
        return cast(Role2StatementSnapshot | None, self._store["snapshots"].get(key))

    async def get_statement_lines(self, snapshot_id: UUID) -> Sequence[Role2StatementLine]:
        lines = self._store["statement_lines"].get(snapshot_id, [])
        return cast(Sequence[Role2StatementLine], lines)

    async def save_statement_snapshot(self, statement: DomainStatement) -> Role2StatementSnapshot:
        key = self._scope_key(statement.snapshot_id)
        snap_row = Role2StatementSnapshot(
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            legal_entity_id=self.legal_entity_id,
            snapshot_id=statement.snapshot_id,
            accounting_period_id=statement.accounting_period_id,
            statement_type=statement.statement_type,
            currency=statement.currency,
            as_of=statement.as_of,
            status=statement.status,
        )
        self._store["snapshots"][key] = snap_row

        stored_lines = []
        for line in statement.lines:
            line_row = Role2StatementLine(
                tenant_id=self.tenant_id,
                organization_id=self.organization_id,
                legal_entity_id=self.legal_entity_id,
                snapshot_id=statement.snapshot_id,
                line_id=line.line_id,
                account_reference=line.account_reference,
                label=line.label,
                amount=line.amount,
                currency=line.currency,
                ledger_references=[ref.model_dump(mode="json") for ref in line.ledger_references],
            )
            stored_lines.append(line_row)
        self._store["statement_lines"][statement.snapshot_id] = stored_lines
        return snap_row
