"""Async database repository for Role 2 with mandatory multi-tenant scoping."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


class Role2Repository:
    def __init__(self, session: AsyncSession, tenant_context: EntityTenantContext) -> None:
        self.session = session
        self.context = tenant_context

    @property
    def tenant_id(self) -> UUID:
        return self.context.tenant_id

    @property
    def organization_id(self) -> UUID:
        return self.context.organization_id

    @property
    def legal_entity_id(self) -> UUID:
        return self.context.legal_entity_id

    def _scope(self, model: type[Any]) -> tuple[Any, ...]:
        return (
            model.tenant_id == self.tenant_id,
            model.organization_id == self.organization_id,
            model.legal_entity_id == self.legal_entity_id,
        )

    def scope_dict(self) -> dict[str, UUID]:
        return {
            "tenant_id": self.tenant_id,
            "organization_id": self.organization_id,
            "legal_entity_id": self.legal_entity_id,
        }

    # ---------------------------------------------------------
    # Chart of Accounts
    # ---------------------------------------------------------
    async def get_account(self, account_code: str) -> Role2Account | None:
        stmt = select(Role2Account).where(
            *self._scope(Role2Account),
            Role2Account.account_code == account_code,
        )
        acc = (await self.session.execute(stmt)).scalar_one_or_none()
        if acc is None and account_code in STANDARD_ACCOUNTS:
            acc = await self.save_account(STANDARD_ACCOUNTS[account_code])
        return acc

    async def list_accounts(self) -> Sequence[Role2Account]:
        stmt = select(Role2Account).where(*self._scope(Role2Account))
        accounts = list((await self.session.execute(stmt)).scalars().all())
        if not accounts:
            for acc in STANDARD_ACCOUNTS.values():
                await self.save_account(acc)
            stmt = select(Role2Account).where(*self._scope(Role2Account))
            accounts = list((await self.session.execute(stmt)).scalars().all())
        return accounts

    async def save_account(self, account: Account) -> Role2Account:
        existing = await self.get_account(account.account_code)
        if existing is not None:
            existing.account_name = account.account_name
            existing.account_type = account.account_type
            existing.normal_balance = account.normal_balance
            existing.currency = account.currency
            existing.is_active = account.is_active
            existing.description = account.description
            await self.session.flush()
            return existing

        row = Role2Account(
            **self.scope_dict(),
            account_code=account.account_code,
            account_name=account.account_name,
            account_type=account.account_type,
            normal_balance=account.normal_balance,
            currency=account.currency,
            is_active=account.is_active,
            description=account.description,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    # ---------------------------------------------------------
    # Accounting Periods
    # ---------------------------------------------------------
    async def get_period(
        self, period_id: UUID, *, lock: bool = False
    ) -> Role2AccountingPeriod | None:
        stmt = select(Role2AccountingPeriod).where(
            *self._scope(Role2AccountingPeriod),
            Role2AccountingPeriod.id == period_id,
        )
        if lock:
            stmt = stmt.with_for_update()
        period = (await self.session.execute(stmt)).scalar_one_or_none()
        if period is None:
            try:
                from sqlalchemy import text

                res = await self.session.execute(
                    text(
                        "SELECT period_start, period_end, state FROM accounting_periods "
                        "WHERE id = :pid AND tenant_id = :tid"
                    ),
                    {"pid": period_id, "tid": self.tenant_id},
                )
                row = res.fetchone()
                if row is not None:
                    p_start, p_end, p_state = row[0], row[1], row[2]
                    st = PeriodStatus.CLOSED if str(p_state) == "CLOSED" else PeriodStatus.OPEN
                    period = await self.save_period(
                        period_id=period_id,
                        period_start=p_start,
                        period_end=p_end,
                        state=st,
                    )
            except Exception:
                pass
        return period

    async def save_period(
        self,
        *,
        period_id: UUID,
        period_start: date,
        period_end: date,
        state: PeriodStatus = PeriodStatus.OPEN,
    ) -> Role2AccountingPeriod:
        existing = await self.get_period(period_id)
        if existing is not None:
            return existing
        row = Role2AccountingPeriod(
            **self.scope_dict(),
            id=period_id,
            period_start=period_start,
            period_end=period_end,
            state=state,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    # ---------------------------------------------------------
    # Proposals Registry
    # ---------------------------------------------------------
    async def get_proposal(self, proposal_id: UUID, version: int) -> Role2ProposalRecord | None:
        stmt = select(Role2ProposalRecord).where(
            *self._scope(Role2ProposalRecord),
            Role2ProposalRecord.proposal_id == proposal_id,
            Role2ProposalRecord.proposal_version == version,
        )
        prop = (await self.session.execute(stmt)).scalar_one_or_none()
        if prop is None:
            try:
                from sqlalchemy import text

                res = await self.session.execute(
                    text(
                        "SELECT proposed_journal_date, currency, explanation, contract_payload "
                        "FROM journal_proposals "
                        "WHERE (id = :pid OR proposal_series_id = :pid) "
                        "AND proposal_version = :ver AND tenant_id = :tid"
                    ),
                    {"pid": proposal_id, "ver": version, "tid": self.tenant_id},
                )
                row = res.fetchone()
                if row is not None:
                    p_date, p_curr, p_exp, p_payload = row[0], row[1], row[2], row[3]
                    lines = []
                    evidence = []
                    if isinstance(p_payload, dict):
                        lines = p_payload.get("lines", [])
                        evidence = p_payload.get("source_evidence", [])
                    row_rec = Role2ProposalRecord(
                        **self.scope_dict(),
                        proposal_id=proposal_id,
                        proposal_version=version,
                        proposed_journal_date=p_date,
                        currency=p_curr,
                        explanation=p_exp,
                        lines_payload=lines,
                        source_evidence=evidence,
                        approval_decision=None,
                    )
                    self.session.add(row_rec)
                    await self.session.flush()
                    prop = row_rec
            except Exception:
                pass
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
        stmt = select(Role2ProposalRecord).where(
            *self._scope(Role2ProposalRecord),
            Role2ProposalRecord.proposal_id == proposal_id,
            Role2ProposalRecord.proposal_version == proposal_version,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing
        row = Role2ProposalRecord(
            **self.scope_dict(),
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            proposed_journal_date=proposed_journal_date,
            currency=currency,
            explanation=explanation,
            lines_payload=lines_payload,
            source_evidence=source_evidence,
            approval_decision=approval_decision,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    # ---------------------------------------------------------
    # Posting Operations (State Machine & Idempotency)
    # ---------------------------------------------------------
    async def get_posting_operation(
        self, operation_id: UUID, *, lock: bool = False
    ) -> Role2PostingOperation | None:
        stmt = select(Role2PostingOperation).where(
            *self._scope(Role2PostingOperation),
            Role2PostingOperation.operation_id == operation_id,
        )
        if lock:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

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
        row = Role2PostingOperation(
            **self.scope_dict(),
            operation_id=operation_id,
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            accounting_period_id=accounting_period_id,
            request_hash=request_hash,
            state=state,
            issues=[issue.model_dump(mode="json") for issue in (issues or [])],
        )
        self.session.add(row)
        await self.session.flush()
        return row

    # ---------------------------------------------------------
    # Posted Journals & Ledger Lines
    # ---------------------------------------------------------
    async def get_journal(self, journal_id: UUID) -> Role2PostedJournal | None:
        stmt = select(Role2PostedJournal).where(
            *self._scope(Role2PostedJournal),
            Role2PostedJournal.id == journal_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_journal_by_operation(self, operation_id: UUID) -> Role2PostedJournal | None:
        stmt = select(Role2PostedJournal).where(
            *self._scope(Role2PostedJournal),
            Role2PostedJournal.operation_id == operation_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_journal_with_lines(self, journal: DomainJournal) -> Role2PostedJournal:
        journal_row = Role2PostedJournal(
            **self.scope_dict(),
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
        self.session.add(journal_row)
        await self.session.flush()

        for idx, line in enumerate(journal.lines, start=1):
            line_row = Role2JournalLine(
                **self.scope_dict(),
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
            self.session.add(line_row)

        await self.session.flush()
        return journal_row

    async def mark_journal_reversed(self, journal_id: UUID) -> None:
        journal = await self.get_journal(journal_id)
        if journal is not None:
            journal.is_reversed = True
            await self.session.flush()

    async def list_domain_journals_for_period(self, period_id: UUID) -> list[DomainJournal]:
        stmt = (
            select(Role2PostedJournal)
            .where(
                *self._scope(Role2PostedJournal),
                Role2PostedJournal.accounting_period_id == period_id,
            )
            .order_by(Role2PostedJournal.journal_date, Role2PostedJournal.posted_at)
        )
        journal_rows = (await self.session.execute(stmt)).scalars().all()

        domain_journals: list[DomainJournal] = []
        for j in journal_rows:
            lines_stmt = (
                select(Role2JournalLine)
                .where(
                    *self._scope(Role2JournalLine),
                    Role2JournalLine.journal_id == j.id,
                )
                .order_by(Role2JournalLine.line_number)
            )
            line_rows = (await self.session.execute(lines_stmt)).scalars().all()

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
                for line in line_rows
            ]

            domain_journals.append(
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
        return domain_journals

    # ---------------------------------------------------------
    # Period Close Operations
    # ---------------------------------------------------------
    async def get_close_operation(self, operation_id: UUID) -> Role2PeriodCloseOperation | None:
        stmt = select(Role2PeriodCloseOperation).where(
            *self._scope(Role2PeriodCloseOperation),
            Role2PeriodCloseOperation.operation_id == operation_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

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
        row = Role2PeriodCloseOperation(
            **self.scope_dict(),
            operation_id=operation_id,
            accounting_period_id=accounting_period_id,
            state=state,
            request_hash=request_hash,
            closed_at=closed_at,
            issues=[issue.model_dump(mode="json") for issue in (issues or [])],
        )
        self.session.add(row)
        await self.session.flush()
        return row

    # ---------------------------------------------------------
    # Statement Snapshots & Lines
    # ---------------------------------------------------------
    async def get_statement_snapshot(self, snapshot_id: UUID) -> Role2StatementSnapshot | None:
        stmt = select(Role2StatementSnapshot).where(
            *self._scope(Role2StatementSnapshot),
            Role2StatementSnapshot.snapshot_id == snapshot_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_statement_lines(self, snapshot_id: UUID) -> Sequence[Role2StatementLine]:
        stmt = (
            select(Role2StatementLine)
            .where(
                *self._scope(Role2StatementLine),
                Role2StatementLine.snapshot_id == snapshot_id,
            )
            .order_by(Role2StatementLine.id)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def save_statement_snapshot(self, statement: DomainStatement) -> Role2StatementSnapshot:
        snap_row = Role2StatementSnapshot(
            **self.scope_dict(),
            snapshot_id=statement.snapshot_id,
            accounting_period_id=statement.accounting_period_id,
            statement_type=statement.statement_type,
            currency=statement.currency,
            as_of=statement.as_of,
            status=statement.status,
        )
        self.session.add(snap_row)
        await self.session.flush()

        for line in statement.lines:
            line_row = Role2StatementLine(
                **self.scope_dict(),
                snapshot_id=statement.snapshot_id,
                line_id=line.line_id,
                account_reference=line.account_reference,
                label=line.label,
                amount=line.amount,
                currency=line.currency,
                ledger_references=[ref.model_dump(mode="json") for ref in line.ledger_references],
            )
            self.session.add(line_row)

        await self.session.flush()
        return snap_row
