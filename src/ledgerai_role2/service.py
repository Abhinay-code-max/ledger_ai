"""Application service implementing deterministic Role 2 accounting operations."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from ledgerai_contracts.v1.accounting import (
    AccountingValidationResult,
    FinancialStatementLine,
    FinancialStatementSnapshot,
    JournalPostingResult,
    PeriodCloseResult,
    PeriodCloseValidationResult,
    PostingStatusResult,
)
from ledgerai_contracts.v1.common import (
    CorrelationMetadata,
    Money,
    ProducerMetadata,
    ProducerType,
    ProvenanceReference,
    ResourceReference,
    ValidationIssue,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role2.database.in_memory import InMemoryRole2Repository
from ledgerai_role2.database.repository import Role2Repository
from ledgerai_role2.domain.calculator import (
    calculate_balance_sheet,
    calculate_profit_and_loss,
    calculate_trial_balance,
)
from ledgerai_role2.domain.invariants import (
    validate_journal_lines,
    validate_period_for_posting,
)
from ledgerai_role2.domain.models import (
    Account,
    Direction,
    DomainJournal,
    DomainJournalLine,
    PeriodStatus,
    StatementType,
)
from ledgerai_role2.domain.reversal import create_reversal_journal
from ledgerai_role2.domain.state_machine import (
    IdempotencyConflictError,
    PostingState,
    compute_payload_hash,
)


class Role2Service:
    def __init__(
        self,
        repository: Role2Repository | InMemoryRole2Repository,
        *,
        service_version: str = "2.0.0",
    ) -> None:
        self.repo = repository
        self.service_version = service_version

    @property
    def tenant_context(self) -> EntityTenantContext:
        return self.repo.context

    def _producer(self) -> ProducerMetadata:
        return ProducerMetadata(
            producer_type=ProducerType.SERVICE,
            name="role2-financial-core",
            version=self.service_version,
        )

    def _default_correlation(
        self, operation_id: UUID, correlation_id: UUID | None = None
    ) -> CorrelationMetadata:
        corr = correlation_id or operation_id
        return CorrelationMetadata(
            request_id=operation_id,
            correlation_id=corr,
            causation_id=None,
        )

    async def _load_accounts_map(self) -> dict[str, Account]:
        db_accounts = await self.repo.list_accounts()
        result: dict[str, Account] = {}
        for a in db_accounts:
            result[a.account_code] = Account(
                account_code=a.account_code,
                account_name=a.account_name,
                account_type=a.account_type,
                normal_balance=a.normal_balance,
                currency=a.currency,
                is_active=a.is_active,
                description=a.description,
            )
        return result

    # ---------------------------------------------------------
    # Journal Posting Request Acceptance
    # ---------------------------------------------------------
    async def accept_posting_request(
        self,
        *,
        operation_id: UUID,
        proposal_id: UUID,
        proposal_version: int,
        proposed_journal_date: date,
        currency: str,
        explanation: str,
        lines_payload: list[dict[str, Any]],
        source_evidence: list[dict[str, Any]],
        approval_decision: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a journal proposal in the registry and confirm acceptance."""
        await self.repo.save_proposal_record(
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            proposed_journal_date=proposed_journal_date,
            currency=currency,
            explanation=explanation,
            lines_payload=lines_payload,
            source_evidence=source_evidence,
            approval_decision=approval_decision,
        )
        return {
            "schema_version": "1.0",
            "tenant_context": self.tenant_context.model_dump(mode="json"),
            "operation_id": str(operation_id),
            "proposal_id": str(proposal_id),
            "proposal_version": str(proposal_version),
            "accepted": True,
            "validation_reference": f"val-{operation_id}",
        }

    # ---------------------------------------------------------
    # Posting Validation
    # ---------------------------------------------------------
    async def validate_posting(
        self,
        *,
        operation_id: UUID,
        proposal_id: UUID,
        proposal_version: int,
        accounting_period_id: UUID,
        raw_payload: dict[str, Any],
        correlation: CorrelationMetadata | None = None,
        inline_lines: list[DomainJournalLine] | None = None,
        journal_date: date | None = None,
        currency: str | None = None,
    ) -> AccountingValidationResult:
        """Deterministically validate proposal lines against double-entry rules and COA."""
        req_hash = compute_payload_hash(raw_payload)
        existing = await self.repo.get_posting_operation(operation_id)
        if existing is not None:
            if existing.request_hash != req_hash:
                raise IdempotencyConflictError(operation_id)
            outcome_literal = (
                "VALIDATED"
                if existing.state in {PostingState.VALIDATED, PostingState.POSTED}
                else ("REJECTED" if existing.state == PostingState.REJECTED else "UNKNOWN")
            )
            issues_objs = [ValidationIssue.model_validate(iss) for iss in (existing.issues or [])]
            return AccountingValidationResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                proposal_id=proposal_id,
                proposal_version=proposal_version,
                outcome=outcome_literal,  # type: ignore[arg-type]
                issues=issues_objs,
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        # Retrieve proposal details
        proposal_rec = await self.repo.get_proposal(proposal_id, proposal_version)
        lines: list[DomainJournalLine] = []
        actual_currency = currency or "INR"
        actual_date = journal_date or date.today()

        if inline_lines is not None:
            lines = inline_lines
        elif proposal_rec is not None:
            actual_currency = proposal_rec.currency
            actual_date = proposal_rec.proposed_journal_date
            for raw_line in proposal_rec.lines_payload:
                amount_val = raw_line.get("amount", {})
                amt_str = (
                    amount_val.get("amount", "0")
                    if isinstance(amount_val, dict)
                    else str(amount_val)
                )
                ev_list = [
                    ProvenanceReference.model_validate(e)
                    for e in raw_line.get("source_evidence", proposal_rec.source_evidence)
                ]
                lines.append(
                    DomainJournalLine(
                        line_id=UUID(raw_line["line_id"]) if "line_id" in raw_line else uuid4(),
                        account_reference=str(raw_line["account_reference"]),
                        direction=Direction(str(raw_line["direction"])),
                        amount=Decimal(amt_str),
                        currency=raw_line.get("currency", actual_currency),
                        description=raw_line.get("description"),
                        source_evidence=ev_list,
                    )
                )

        accounts_map = await self._load_accounts_map()
        issues: list[ValidationIssue] = []

        # Validate period
        period_row = await self.repo.get_period(accounting_period_id)
        if period_row is None:
            issues.append(
                ValidationIssue(
                    code="PERIOD_NOT_FOUND",
                    message=f"Accounting period '{accounting_period_id}' does not exist.",
                    field="accounting_period_id",
                    severity="ERROR",
                )
            )
        else:
            issues.extend(
                validate_period_for_posting(
                    period_row.period_start,
                    period_row.period_end,
                    period_row.state,
                    actual_date,
                )
            )

        # Validate lines
        if not lines:
            issues.append(
                ValidationIssue(
                    code="NO_JOURNAL_LINES",
                    message="Proposal contains no journal lines to validate.",
                    field="lines",
                    severity="ERROR",
                )
            )
        else:
            issues.extend(validate_journal_lines(lines, actual_currency, accounts_map))

        outcome: Literal["VALIDATED", "REJECTED"] = "VALIDATED" if not issues else "REJECTED"
        op_state = PostingState.VALIDATED if not issues else PostingState.REJECTED

        await self.repo.create_posting_operation(
            operation_id=operation_id,
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            accounting_period_id=accounting_period_id,
            request_hash=req_hash,
            state=op_state,
            issues=issues,
        )

        return AccountingValidationResult(
            schema_version="1.0",
            tenant_context=self.tenant_context,
            operation_id=operation_id,
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            outcome=outcome,
            issues=issues,
            producer=self._producer(),
            correlation=correlation or self._default_correlation(operation_id),
        )

    # ---------------------------------------------------------
    # Idempotent Journal Posting
    # ---------------------------------------------------------
    async def post_journal(
        self,
        *,
        operation_id: UUID,
        proposal_id: UUID,
        proposal_version: int,
        accounting_period_id: UUID,
        raw_payload: dict[str, Any],
        correlation: CorrelationMetadata | None = None,
        inline_lines: list[DomainJournalLine] | None = None,
        journal_date: date | None = None,
        currency: str | None = None,
        explanation: str | None = None,
    ) -> JournalPostingResult:
        """Atomically post an immutable double-entry journal entry."""
        req_hash = compute_payload_hash(raw_payload)
        existing = await self.repo.get_posting_operation(operation_id, lock=True)

        if existing is not None:
            if existing.request_hash != req_hash:
                raise IdempotencyConflictError(operation_id)
            if existing.state == PostingState.POSTED:
                # Idempotent return of existing posted result
                assert existing.posted_journal_id is not None
                assert existing.posted_at is not None
                return JournalPostingResult(
                    schema_version="1.0",
                    tenant_context=self.tenant_context,
                    operation_id=operation_id,
                    proposal_id=proposal_id,
                    proposal_version=proposal_version,
                    outcome="POSTED",
                    posted_journal_id=existing.posted_journal_id,
                    posted_at=existing.posted_at,
                    ledger_references=[
                        ResourceReference(
                            resource_type="posted_journal",
                            resource_id=UUID(existing.posted_journal_id),
                            resource_version="1",
                        )
                    ],
                    issues=[],
                    producer=self._producer(),
                    correlation=correlation or self._default_correlation(operation_id),
                )
            if existing.state == PostingState.REJECTED:
                issues_objs = [ValidationIssue.model_validate(i) for i in (existing.issues or [])]
                return JournalPostingResult(
                    schema_version="1.0",
                    tenant_context=self.tenant_context,
                    operation_id=operation_id,
                    proposal_id=proposal_id,
                    proposal_version=proposal_version,
                    outcome="REJECTED",
                    posted_journal_id=None,
                    posted_at=None,
                    ledger_references=[],
                    issues=issues_objs,
                    producer=self._producer(),
                    correlation=correlation or self._default_correlation(operation_id),
                )

        # Retrieve proposal details
        proposal_rec = await self.repo.get_proposal(proposal_id, proposal_version)
        lines: list[DomainJournalLine] = []
        actual_currency = currency or "INR"
        actual_date = journal_date or date.today()
        actual_explanation = explanation or "Standard posted journal entry"

        if inline_lines is not None:
            lines = inline_lines
        elif proposal_rec is not None:
            actual_currency = proposal_rec.currency
            actual_date = proposal_rec.proposed_journal_date
            actual_explanation = proposal_rec.explanation
            for raw_line in proposal_rec.lines_payload:
                amount_val = raw_line.get("amount", {})
                amt_str = (
                    amount_val.get("amount", "0")
                    if isinstance(amount_val, dict)
                    else str(amount_val)
                )
                ev_list = [
                    ProvenanceReference.model_validate(e)
                    for e in raw_line.get("source_evidence", proposal_rec.source_evidence)
                ]
                lines.append(
                    DomainJournalLine(
                        line_id=UUID(raw_line["line_id"]) if "line_id" in raw_line else uuid4(),
                        account_reference=str(raw_line["account_reference"]),
                        direction=Direction(str(raw_line["direction"])),
                        amount=Decimal(amt_str),
                        currency=raw_line.get("currency", actual_currency),
                        description=raw_line.get("description"),
                        source_evidence=ev_list,
                    )
                )

        accounts_map = await self._load_accounts_map()
        issues: list[ValidationIssue] = []

        # Validate period
        period_row = await self.repo.get_period(accounting_period_id)
        if period_row is None:
            issues.append(
                ValidationIssue(
                    code="PERIOD_NOT_FOUND",
                    message=f"Accounting period '{accounting_period_id}' does not exist.",
                    field="accounting_period_id",
                    severity="ERROR",
                )
            )
        else:
            issues.extend(
                validate_period_for_posting(
                    period_row.period_start,
                    period_row.period_end,
                    period_row.state,
                    actual_date,
                )
            )

        # Validate lines
        if not lines:
            issues.append(
                ValidationIssue(
                    code="NO_JOURNAL_LINES",
                    message="Proposal contains no journal lines to post.",
                    field="lines",
                    severity="ERROR",
                )
            )
        else:
            issues.extend(validate_journal_lines(lines, actual_currency, accounts_map))

        if issues:
            if existing is not None:
                existing.state = PostingState.REJECTED
                existing.issues = [i.model_dump(mode="json") for i in issues]
            else:
                await self.repo.create_posting_operation(
                    operation_id=operation_id,
                    proposal_id=proposal_id,
                    proposal_version=proposal_version,
                    accounting_period_id=accounting_period_id,
                    request_hash=req_hash,
                    state=PostingState.REJECTED,
                    issues=issues,
                )
            return JournalPostingResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                proposal_id=proposal_id,
                proposal_version=proposal_version,
                outcome="REJECTED",
                posted_journal_id=None,
                posted_at=None,
                ledger_references=[],
                issues=issues,
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        # Validated: Post atomic immutable journal
        now_utc = datetime.now(UTC)
        journal_id = uuid4()
        corr_id = correlation.correlation_id if correlation else operation_id

        domain_journal = DomainJournal(
            journal_id=journal_id,
            operation_id=operation_id,
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            accounting_period_id=accounting_period_id,
            journal_date=actual_date,
            currency=actual_currency,
            explanation=actual_explanation,
            lines=lines,
            posted_at=now_utc,
            correlation_id=corr_id,
        )

        await self.repo.save_journal_with_lines(domain_journal)

        if existing is not None:
            existing.state = PostingState.POSTED
            existing.posted_journal_id = str(journal_id)
            existing.posted_at = now_utc
            existing.issues = []
        else:
            op_row = await self.repo.create_posting_operation(
                operation_id=operation_id,
                proposal_id=proposal_id,
                proposal_version=proposal_version,
                accounting_period_id=accounting_period_id,
                request_hash=req_hash,
                state=PostingState.POSTED,
                issues=[],
            )
            op_row.posted_journal_id = str(journal_id)
            op_row.posted_at = now_utc

        return JournalPostingResult(
            schema_version="1.0",
            tenant_context=self.tenant_context,
            operation_id=operation_id,
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            outcome="POSTED",
            posted_journal_id=str(journal_id),
            posted_at=now_utc,
            ledger_references=[
                ResourceReference(
                    resource_type="posted_journal",
                    resource_id=journal_id,
                    resource_version="1",
                )
            ],
            issues=[],
            producer=self._producer(),
            correlation=correlation or self._default_correlation(operation_id),
        )

    # ---------------------------------------------------------
    # Posting Status Lookup
    # ---------------------------------------------------------
    async def get_posting_status(
        self,
        *,
        operation_id: UUID,
        correlation: CorrelationMetadata | None = None,
    ) -> PostingStatusResult:
        """Lookup operation status explicitly distinguishing pending, posted, rejected, unknown."""
        op_row = await self.repo.get_posting_operation(operation_id)
        if op_row is None:
            # Check if journal exists by operation_id directly (recovery case)
            journal = await self.repo.get_journal_by_operation(operation_id)
            if journal is not None:
                return PostingStatusResult(
                    schema_version="1.0",
                    tenant_context=self.tenant_context,
                    operation_id=operation_id,
                    proposal_id=journal.proposal_id,
                    proposal_version=journal.proposal_version,
                    outcome="POSTED",
                    posted_journal_id=str(journal.id),
                    posted_at=journal.posted_at,
                    ledger_references=[
                        ResourceReference(
                            resource_type="posted_journal",
                            resource_id=journal.id,
                            resource_version="1",
                        )
                    ],
                    issues=[],
                    producer=self._producer(),
                    correlation=correlation or self._default_correlation(operation_id),
                )
            return PostingStatusResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                proposal_id=uuid4(),
                proposal_version=1,
                outcome="UNKNOWN",
                posted_journal_id=None,
                posted_at=None,
                ledger_references=[],
                issues=[
                    ValidationIssue(
                        code="OPERATION_NOT_FOUND",
                        message=f"Operation '{operation_id}' was not found in Role 2.",
                        severity="ERROR",
                    )
                ],
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        if op_row.state == PostingState.POSTED:
            assert op_row.posted_journal_id is not None
            assert op_row.posted_at is not None
            return PostingStatusResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                proposal_id=op_row.proposal_id,
                proposal_version=op_row.proposal_version,
                outcome="POSTED",
                posted_journal_id=op_row.posted_journal_id,
                posted_at=op_row.posted_at,
                ledger_references=[
                    ResourceReference(
                        resource_type="posted_journal",
                        resource_id=UUID(op_row.posted_journal_id),
                        resource_version="1",
                    )
                ],
                issues=[],
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        if op_row.state == PostingState.REJECTED:
            issues = [ValidationIssue.model_validate(i) for i in (op_row.issues or [])]
            return PostingStatusResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                proposal_id=op_row.proposal_id,
                proposal_version=op_row.proposal_version,
                outcome="REJECTED",
                posted_journal_id=None,
                posted_at=None,
                ledger_references=[],
                issues=issues,
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        outcome_val = (
            "IN_PROGRESS"
            if op_row.state
            in {PostingState.PENDING, PostingState.IN_PROGRESS, PostingState.VALIDATED}
            else ("FAILED" if op_row.state == PostingState.FAILED else "UNKNOWN")
        )
        return PostingStatusResult(
            schema_version="1.0",
            tenant_context=self.tenant_context,
            operation_id=operation_id,
            proposal_id=op_row.proposal_id,
            proposal_version=op_row.proposal_version,
            outcome=outcome_val,  # type: ignore[arg-type]
            posted_journal_id=None,
            posted_at=None,
            ledger_references=[],
            issues=[],
            producer=self._producer(),
            correlation=correlation or self._default_correlation(operation_id),
        )

    # ---------------------------------------------------------
    # Period Close Workflow
    # ---------------------------------------------------------
    async def validate_period_close(
        self,
        *,
        operation_id: UUID,
        accounting_period_id: UUID,
        correlation: CorrelationMetadata | None = None,
    ) -> PeriodCloseValidationResult:
        """Verify close prerequisites: all postings confirmed, TB balanced, period open."""
        period = await self.repo.get_period(accounting_period_id)
        issues: list[ValidationIssue] = []

        if period is None:
            issues.append(
                ValidationIssue(
                    code="PERIOD_NOT_FOUND",
                    message="Accounting period not found.",
                    severity="ERROR",
                )
            )
            return PeriodCloseValidationResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                accounting_period_id=accounting_period_id,
                outcome="REJECTED",
                issues=issues,
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        if period.state == PeriodStatus.CLOSED:
            issues.append(
                ValidationIssue(
                    code="PERIOD_ALREADY_CLOSED",
                    message="Accounting period is already closed.",
                    severity="ERROR",
                )
            )
            return PeriodCloseValidationResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                accounting_period_id=accounting_period_id,
                outcome="BLOCKED",
                issues=issues,
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        # Check Trial balance balance
        accounts_map = await self._load_accounts_map()
        journals = await self.repo.list_domain_journals_for_period(accounting_period_id)
        tb = calculate_trial_balance(
            accounts_map,
            journals,
            accounting_period_id=accounting_period_id,
            as_of=datetime.now(UTC),
            currency="INR",
        )
        debit_line = next((ln for ln in tb.lines if ln.account_reference == "TOTAL_DEBITS"), None)
        credit_line = next((ln for ln in tb.lines if ln.account_reference == "TOTAL_CREDITS"), None)

        if debit_line and credit_line and debit_line.amount != credit_line.amount:
            issues.append(
                ValidationIssue(
                    code="TRIAL_BALANCE_UNBALANCED",
                    message=(
                        f"Trial balance unbalanced: Debits={debit_line.amount}, "
                        f"Credits={credit_line.amount}"
                    ),
                    severity="ERROR",
                )
            )

        outcome: Literal["VALIDATED", "BLOCKED"] = "VALIDATED" if not issues else "BLOCKED"
        return PeriodCloseValidationResult(
            schema_version="1.0",
            tenant_context=self.tenant_context,
            operation_id=operation_id,
            accounting_period_id=accounting_period_id,
            outcome=outcome,
            issues=issues,
            producer=self._producer(),
            correlation=correlation or self._default_correlation(operation_id),
        )

    async def close_period(
        self,
        *,
        operation_id: UUID,
        accounting_period_id: UUID,
        raw_payload: dict[str, Any],
        correlation: CorrelationMetadata | None = None,
    ) -> PeriodCloseResult:
        """Deterministically close an accounting period and generate statements."""
        req_hash = compute_payload_hash(raw_payload)
        existing_close = await self.repo.get_close_operation(operation_id)
        if existing_close is not None:
            if existing_close.request_hash != req_hash:
                raise IdempotencyConflictError(operation_id)
            if existing_close.state == "CLOSED":
                return PeriodCloseResult(
                    schema_version="1.0",
                    tenant_context=self.tenant_context,
                    operation_id=operation_id,
                    accounting_period_id=accounting_period_id,
                    outcome="CLOSED",
                    issues=[],
                    closed_at=existing_close.closed_at,
                    producer=self._producer(),
                    correlation=correlation or self._default_correlation(operation_id),
                )
            if existing_close.state == "BLOCKED":
                issues = [ValidationIssue.model_validate(i) for i in (existing_close.issues or [])]
                return PeriodCloseResult(
                    schema_version="1.0",
                    tenant_context=self.tenant_context,
                    operation_id=operation_id,
                    accounting_period_id=accounting_period_id,
                    outcome="BLOCKED",
                    issues=issues,
                    closed_at=None,
                    producer=self._producer(),
                    correlation=correlation or self._default_correlation(operation_id),
                )

        val_res = await self.validate_period_close(
            operation_id=operation_id,
            accounting_period_id=accounting_period_id,
            correlation=correlation,
        )
        if val_res.outcome != "VALIDATED":
            await self.repo.create_close_operation(
                operation_id=operation_id,
                accounting_period_id=accounting_period_id,
                state="BLOCKED",
                request_hash=req_hash,
                issues=val_res.issues,
            )
            return PeriodCloseResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                accounting_period_id=accounting_period_id,
                outcome="BLOCKED",
                issues=val_res.issues,
                closed_at=None,
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        now_utc = datetime.now(UTC)
        period = await self.repo.get_period(accounting_period_id, lock=True)
        assert period is not None
        period.state = PeriodStatus.CLOSED
        period.closed_at = now_utc
        period.closed_by = "role2-financial-core"

        await self.repo.create_close_operation(
            operation_id=operation_id,
            accounting_period_id=accounting_period_id,
            state="CLOSED",
            request_hash=req_hash,
            closed_at=now_utc,
            issues=[],
        )

        return PeriodCloseResult(
            schema_version="1.0",
            tenant_context=self.tenant_context,
            operation_id=operation_id,
            accounting_period_id=accounting_period_id,
            outcome="CLOSED",
            issues=[],
            closed_at=now_utc,
            producer=self._producer(),
            correlation=correlation or self._default_correlation(operation_id),
        )

    async def get_period_close_status(
        self,
        *,
        operation_id: UUID,
        correlation: CorrelationMetadata | None = None,
    ) -> PeriodCloseResult:
        """Lookup status of a period close operation."""
        close_op = await self.repo.get_close_operation(operation_id)
        if close_op is None:
            return PeriodCloseResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                accounting_period_id=uuid4(),
                outcome="UNKNOWN",
                issues=[
                    ValidationIssue(
                        code="CLOSE_OPERATION_NOT_FOUND",
                        message="Period close operation not found.",
                        severity="ERROR",
                    )
                ],
                closed_at=None,
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        issues = [ValidationIssue.model_validate(i) for i in (close_op.issues or [])]
        return PeriodCloseResult(
            schema_version="1.0",
            tenant_context=self.tenant_context,
            operation_id=operation_id,
            accounting_period_id=close_op.accounting_period_id,
            outcome=close_op.state,  # type: ignore[arg-type]
            issues=issues,
            closed_at=close_op.closed_at,
            producer=self._producer(),
            correlation=correlation or self._default_correlation(operation_id),
        )

    # ---------------------------------------------------------
    # Immutable Financial Statements
    # ---------------------------------------------------------
    async def generate_statement(
        self,
        *,
        operation_id: UUID,
        accounting_period_id: UUID,
        statement_type: str,
        as_of: datetime,
        currency: str = "INR",
        correlation: CorrelationMetadata | None = None,
    ) -> FinancialStatementSnapshot:
        """Generate and store an immutable financial statement snapshot."""
        accounts_map = await self._load_accounts_map()
        journals = await self.repo.list_domain_journals_for_period(accounting_period_id)

        st_type = StatementType(statement_type)
        snapshot_id = uuid4()

        if st_type == StatementType.TRIAL_BALANCE:
            domain_stmt = calculate_trial_balance(
                accounts_map,
                journals,
                accounting_period_id=accounting_period_id,
                as_of=as_of,
                currency=currency,
                snapshot_id=snapshot_id,
            )
        elif st_type == StatementType.PROFIT_AND_LOSS:
            domain_stmt, _ = calculate_profit_and_loss(
                accounts_map,
                journals,
                accounting_period_id=accounting_period_id,
                as_of=as_of,
                currency=currency,
                snapshot_id=snapshot_id,
            )
        elif st_type == StatementType.BALANCE_SHEET:
            _, net_income = calculate_profit_and_loss(
                accounts_map,
                journals,
                accounting_period_id=accounting_period_id,
                as_of=as_of,
                currency=currency,
            )
            domain_stmt = calculate_balance_sheet(
                accounts_map,
                journals,
                net_income,
                accounting_period_id=accounting_period_id,
                as_of=as_of,
                currency=currency,
                snapshot_id=snapshot_id,
            )
        else:
            raise ValueError(f"Unsupported statement type: {statement_type}")

        # Persist snapshot and lines
        await self.repo.save_statement_snapshot(domain_stmt)

        stmt_lines = [
            FinancialStatementLine(
                line_id=line.line_id,
                account_reference=line.account_reference,
                label=line.label,
                amount=Money(amount=line.amount, currency=line.currency),
                ledger_references=line.ledger_references,
            )
            for line in domain_stmt.lines
        ]

        return FinancialStatementSnapshot(
            schema_version="1.0",
            snapshot_id=domain_stmt.snapshot_id,
            tenant_context=self.tenant_context,
            accounting_period_id=accounting_period_id,
            statement_type=statement_type,  # type: ignore[arg-type]
            currency=currency,
            as_of=as_of,
            status="AVAILABLE",
            lines=stmt_lines,
            producer=self._producer(),
            correlation=correlation or self._default_correlation(operation_id),
        )

    # ---------------------------------------------------------
    # Reversals and Correcting Entries
    # ---------------------------------------------------------
    async def reverse_posted_journal(
        self,
        *,
        operation_id: UUID,
        journal_id: UUID,
        accounting_period_id: UUID,
        reversal_date: date,
        reason: str,
        correlation: CorrelationMetadata | None = None,
    ) -> JournalPostingResult:
        """Create an exact reversing journal with inverted lines."""
        journal = await self.repo.get_journal(journal_id)
        if journal is None:
            return JournalPostingResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                proposal_id=uuid4(),
                proposal_version=1,
                outcome="REJECTED",
                posted_journal_id=None,
                posted_at=None,
                ledger_references=[],
                issues=[
                    ValidationIssue(
                        code="JOURNAL_NOT_FOUND",
                        message=f"Journal '{journal_id}' not found for reversal.",
                        severity="ERROR",
                    )
                ],
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        if journal.is_reversed:
            return JournalPostingResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                proposal_id=journal.proposal_id,
                proposal_version=journal.proposal_version,
                outcome="REJECTED",
                posted_journal_id=None,
                posted_at=None,
                ledger_references=[],
                issues=[
                    ValidationIssue(
                        code="ALREADY_REVERSED",
                        message=f"Journal '{journal_id}' has already been reversed.",
                        severity="ERROR",
                    )
                ],
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        # Check reversal period is open
        period = await self.repo.get_period(accounting_period_id)
        if period is None or period.state != PeriodStatus.OPEN:
            return JournalPostingResult(
                schema_version="1.0",
                tenant_context=self.tenant_context,
                operation_id=operation_id,
                proposal_id=journal.proposal_id,
                proposal_version=journal.proposal_version,
                outcome="REJECTED",
                posted_journal_id=None,
                posted_at=None,
                ledger_references=[],
                issues=[
                    ValidationIssue(
                        code="PERIOD_NOT_OPEN",
                        message="Reversal entries must be posted to an open accounting period.",
                        severity="ERROR",
                    )
                ],
                producer=self._producer(),
                correlation=correlation or self._default_correlation(operation_id),
            )

        # Reconstruct DomainJournal from lines
        journals_list = await self.repo.list_domain_journals_for_period(
            journal.accounting_period_id
        )
        original_domain = next((j for j in journals_list if j.journal_id == journal_id), None)
        assert original_domain is not None

        now_utc = datetime.now(UTC)
        reversal_domain = create_reversal_journal(
            original_domain,
            reversal_operation_id=operation_id,
            accounting_period_id=accounting_period_id,
            reversal_date=reversal_date,
            now=now_utc,
            reason=reason,
            correlation_id=correlation.correlation_id if correlation else operation_id,
        )

        await self.repo.save_journal_with_lines(reversal_domain)
        await self.repo.mark_journal_reversed(journal_id)

        await self.repo.create_posting_operation(
            operation_id=operation_id,
            proposal_id=journal.proposal_id,
            proposal_version=journal.proposal_version,
            accounting_period_id=accounting_period_id,
            request_hash=compute_payload_hash(
                {"journal_id": str(journal_id), "op": str(operation_id)}
            ),
            state=PostingState.POSTED,
            issues=[],
        )

        return JournalPostingResult(
            schema_version="1.0",
            tenant_context=self.tenant_context,
            operation_id=operation_id,
            proposal_id=journal.proposal_id,
            proposal_version=journal.proposal_version,
            outcome="POSTED",
            posted_journal_id=str(reversal_domain.journal_id),
            posted_at=now_utc,
            ledger_references=[
                ResourceReference(
                    resource_type="posted_journal",
                    resource_id=reversal_domain.journal_id,
                    resource_version="1",
                )
            ],
            issues=[],
            producer=self._producer(),
            correlation=correlation or self._default_correlation(operation_id),
        )
