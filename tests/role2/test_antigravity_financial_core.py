"""Independent adversarial QA test suite for LedgerAI Role 2 financial core.

All expected values and accounting invariants are derived independently from
standard financial accounting principles and explicit contract requirements.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from financial_core import Account, AccountingError, FinancialEngine
from financial_core.money import decimal_amount, minor_units
from financial_core.templates import demo_proposal
from ledgerai_contracts.v1.approvals import ApprovalDecision
from ledgerai_contracts.v1.common import ResourceReference
from ledgerai_contracts.v1.journals import JournalProposal

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "shared/fixtures/contracts/v1"

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
ORG_ID = UUID("22222222-2222-2222-2222-222222222222")
LEGAL_ENTITY_ID = UUID("33333333-3333-3333-3333-333333333333")

DATE_2026_01_01 = date(2026, 1, 1)
DATE_2026_01_05 = date(2026, 1, 5)
DATE_2026_01_09 = date(2026, 1, 9)
DATE_2026_01_10 = date(2026, 1, 10)
DATE_2026_01_12 = date(2026, 1, 12)
DATE_2026_01_14 = date(2026, 1, 14)
DATE_2026_01_15 = date(2026, 1, 15)
DATE_2026_01_20 = date(2026, 1, 20)
DATE_2026_01_31 = date(2026, 1, 31)
DATE_2026_02_01 = date(2026, 2, 1)
DATE_2026_02_02 = date(2026, 2, 2)
DATE_2026_02_15 = date(2026, 2, 15)
DATE_2026_02_28 = date(2026, 2, 28)
DATE_2026_03_01 = date(2026, 3, 1)


def sample_proposal(
    amount_str: str = "1250.00",
    currency: str = "INR",
    journal_date: date = DATE_2026_01_15,
    proposal_id: UUID | None = None,
) -> JournalProposal:
    payload = json.loads((FIXTURES_DIR / "journal-proposal.unposted.json").read_text())
    payload["currency"] = currency
    payload["proposed_journal_date"] = journal_date.isoformat()
    if proposal_id is not None:
        payload["proposal_id"] = str(proposal_id)
    else:
        payload["proposal_id"] = str(uuid4())
    for line in payload["lines"]:
        line["amount"]["currency"] = currency
        line["amount"]["amount"] = amount_str
    return JournalProposal.model_validate(payload)


def sample_approval(proposal: JournalProposal) -> ApprovalDecision:
    payload = json.loads((FIXTURES_DIR / "approval-decision.approved.json").read_text())
    payload["tenant_context"] = proposal.tenant_context.model_dump(mode="json")
    payload["reviewed_resource"]["resource_id"] = str(proposal.proposal_id)
    payload["reviewed_resource"]["resource_version"] = str(proposal.proposal_version)
    return ApprovalDecision.model_validate(payload)


def standard_chart() -> list[Account]:
    return [
        Account("CASH", "Cash and Equivalents", "ASSET"),
        Account("AR", "Accounts Receivable", "ASSET"),
        Account("PAYABLE", "Accounts Payable", "LIABILITY"),
        Account("CAPITAL", "Contributed Capital", "EQUITY"),
        Account("REVENUE", "Sales Revenue", "REVENUE"),
        Account("EXPENSE", "Operating Expense", "EXPENSE"),
        Account("SYNTH-EXPENSE", "Synthetic Expense", "EXPENSE"),
        Account("SYNTH-PAYABLE", "Synthetic Payable", "LIABILITY"),
        Account("INACTIVE-ASSET", "Obsolete Asset", "ASSET", active=False),
    ]


def standard_engine(scales: dict[str, int] | None = None) -> FinancialEngine:
    if scales is None:
        scales = {"INR": 2, "USD": 2, "JPY": 0, "KWD": 3}
    return FinancialEngine(sample_proposal().tenant_context, standard_chart(), scales)


# ==============================================================================
# 1. MONEY TESTS
# ==============================================================================


class TestMoneyCalculations:
    """Rigorous independent testing of exact money and currency precision."""

    @pytest.mark.parametrize(
        "amount_str,scale,expected_units",
        [
            ("0.01", 2, 1),
            ("1.00", 2, 100),
            ("12.50", 2, 1250),
            ("12.500", 2, 1250),
            ("12.5000", 2, 1250),
            ("500", 0, 500),
            ("500.0", 0, 500),
            ("0.001", 3, 1),
            ("1.234", 3, 1234),
            ("1.2340", 3, 1234),
            ("999999999999999999999999999999.99", 2, 99999999999999999999999999999999),
        ],
    )
    def test_exact_minor_units_conversion(
        self, amount_str: str, scale: int, expected_units: int
    ) -> None:
        assert minor_units(amount_str, scale) == expected_units
        assert minor_units(Decimal(amount_str), scale) == expected_units

    def test_exact_sums_under_low_decimal_context_precision(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 1
            units = minor_units("12345.67", 2)
            assert units == 1234567
            dec = decimal_amount(units, 2)
            assert dec == Decimal("12345.67")

    @pytest.mark.parametrize(
        "zero_amount",
        ["0", "0.0", "0.00", "0.000", Decimal("0"), Decimal("0.00")],
    )
    def test_reject_zero_amounts(self, zero_amount: str | Decimal) -> None:
        with pytest.raises(AccountingError, match="INVALID_MONEY"):
            minor_units(zero_amount, 2)

    @pytest.mark.parametrize(
        "neg_amount",
        ["-1", "-0.01", "-100.50", Decimal("-1"), Decimal("-0.01")],
    )
    def test_reject_negative_amounts(self, neg_amount: str | Decimal) -> None:
        with pytest.raises(AccountingError, match="INVALID_MONEY"):
            minor_units(neg_amount, 2)

    @pytest.mark.parametrize(
        "bad_type",
        [100, 100.5, True, False, None, [100], {"amount": "100"}],
    )
    def test_reject_non_str_non_decimal_types(self, bad_type: object) -> None:
        with pytest.raises(AccountingError, match="INVALID_MONEY"):
            minor_units(bad_type, 2)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "special_decimal",
        [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("sNaN")],
    )
    def test_reject_nan_and_infinity_decimals(self, special_decimal: Decimal) -> None:
        with pytest.raises(AccountingError, match="INVALID_MONEY"):
            minor_units(special_decimal, 2)

    @pytest.mark.parametrize(
        "malformed_str",
        [
            "1e2",
            "1E+5",
            "1e-2",
            ".50",
            "12..34",
            "012.34",
            "1,000.00",
            "100 USD",
            " 100.00",
            "100.00 ",
            "",
            "   ",
        ],
    )
    def test_reject_malformed_and_scientific_strings(self, malformed_str: str) -> None:
        with pytest.raises(AccountingError, match="INVALID_MONEY"):
            minor_units(malformed_str, 2)

    def test_reject_strings_exceeding_100_characters(self) -> None:
        huge_str = "9" * 101
        with pytest.raises(AccountingError, match="INVALID_MONEY"):
            minor_units(huge_str, 2)

    @pytest.mark.parametrize(
        "amount,scale",
        [
            ("10.5", 0),
            ("10.501", 2),
            ("10.1234", 3),
            ("10.0000001", 6),
        ],
    )
    def test_reject_excess_fractional_precision(self, amount: str, scale: int) -> None:
        with pytest.raises(AccountingError, match="CURRENCY_PRECISION"):
            minor_units(amount, scale)

    @pytest.mark.parametrize("invalid_scale", [-1, 7, 10, True, False, 2.5, "2"])
    def test_reject_invalid_scale_parameters(self, invalid_scale: object) -> None:
        with pytest.raises(AccountingError, match="INVALID_CURRENCY_SCALE"):
            minor_units("100", invalid_scale)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "units,scale,expected",
        [
            (0, 0, Decimal("0")),
            (0, 2, Decimal("0.00")),
            (100, 2, Decimal("1.00")),
            (-100, 2, Decimal("-1.00")),
            (5, 2, Decimal("0.05")),
            (-5, 2, Decimal("-0.05")),
            (125, 3, Decimal("0.125")),
            (-125, 3, Decimal("-0.125")),
            (10, 0, Decimal("10")),
            (-10, 0, Decimal("-10")),
        ],
    )
    def test_decimal_amount_presentation(self, units: int, scale: int, expected: Decimal) -> None:
        assert decimal_amount(units, scale) == expected


# ==============================================================================
# 2. JOURNAL VALIDATION TESTS
# ==============================================================================


class TestJournalValidation:
    """Validation of balance, accounts, lines, currency, and evidence."""

    def test_unbalanced_entry_rejected(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        prop.lines[0].amount.amount = Decimal("1250.01")
        with pytest.raises(AccountingError, match="UNBALANCED_JOURNAL"):
            engine.validate_proposal(prop)
        assert engine.general_ledger("INR") == ()

    def test_duplicate_line_ids_rejected(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        prop.lines[1].line_id = prop.lines[0].line_id
        with pytest.raises(AccountingError, match="DUPLICATE_LINE"):
            engine.validate_proposal(prop)
        assert engine.general_ledger("INR") == ()

    def test_missing_and_inactive_accounts_rejected(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()

        prop.lines[0].account_reference = "DOES_NOT_EXIST"
        with pytest.raises(AccountingError, match="ACCOUNT_UNAVAILABLE"):
            engine.validate_proposal(prop)

        prop.lines[0].account_reference = "INACTIVE-ASSET"
        with pytest.raises(AccountingError, match="ACCOUNT_UNAVAILABLE"):
            engine.validate_proposal(prop)
        assert engine.general_ledger("INR") == ()

    def test_header_and_line_currency_mismatch_rejected(self) -> None:
        engine = standard_engine()
        prop = sample_proposal(currency="INR")
        prop.lines[0].amount.currency = "USD"
        with pytest.raises(AccountingError, match="CURRENCY_MISMATCH"):
            engine.validate_proposal(prop)

    def test_unresolvable_line_and_header_evidence_rejected(self) -> None:
        engine = standard_engine()

        prop_bad_line = sample_proposal()
        prop_bad_line.lines[0].source_evidence[0].source_document_id = None
        prop_bad_line.lines[0].source_evidence[0].evidence_hash = None
        prop_bad_line.lines[0].source_evidence[0].human_correction_id = None
        with pytest.raises(AccountingError, match="EVIDENCE_UNRESOLVABLE"):
            engine.validate_proposal(prop_bad_line)

        prop_bad_hdr = sample_proposal()
        prop_bad_hdr.source_evidence[0].source_document_id = None
        prop_bad_hdr.source_evidence[0].evidence_hash = None
        prop_bad_hdr.source_evidence[0].human_correction_id = None
        with pytest.raises(AccountingError, match="EVIDENCE_UNRESOLVABLE"):
            engine.validate_proposal(prop_bad_hdr)

    def test_revalidate_model_constructed_and_copied_mutations(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()

        bad_prop = JournalProposal.model_construct(
            schema_version="1.0",
            proposal_id=uuid4(),
            proposal_version=1,
            tenant_context=prop.tenant_context,
            proposed_journal_date=DATE_2026_01_15,
            currency="INR",
            lines=[],
            source_evidence=prop.source_evidence,
            explanation="constructed invalid",
            producer=prop.producer,
            accounting_validation="NOT_VALIDATED",
            posting_status="UNPOSTED",
            correlation=prop.correlation,
        )
        with pytest.raises(ValidationError):
            engine.validate_proposal(bad_prop)

    def test_rejected_inputs_leave_ledger_state_completely_clean(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        prop.lines[0].amount.amount = Decimal("9999.99")

        with pytest.raises(AccountingError, match="UNBALANCED_JOURNAL"):
            engine.post(prop, sample_approval(prop))

        assert len(engine.general_ledger("INR")) == 0
        assert engine.account_balance("CASH", "INR", DATE_2026_01_31) == Decimal("0.00")


# ==============================================================================
# 3. TENANT AND APPROVAL BOUNDARIES
# ==============================================================================


class TestTenantAndApprovalBoundaries:
    """Validation of entity boundaries, approver identity, actions, and references."""

    @pytest.mark.parametrize(
        "field_to_corrupt",
        ["tenant_id", "organization_id", "legal_entity_id"],
    )
    def test_tenant_context_mismatch_on_proposal(self, field_to_corrupt: str) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        setattr(prop.tenant_context, field_to_corrupt, uuid4())
        app = sample_approval(prop)
        with pytest.raises(AccountingError, match="TENANT_MISMATCH"):
            engine.post(prop, app)

    @pytest.mark.parametrize(
        "field_to_corrupt",
        ["tenant_id", "organization_id", "legal_entity_id"],
    )
    def test_tenant_context_mismatch_on_approval(self, field_to_corrupt: str) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        app = sample_approval(prop)
        setattr(app.tenant_context, field_to_corrupt, uuid4())
        with pytest.raises(AccountingError, match="TENANT_MISMATCH"):
            engine.post(prop, app)

    def test_approval_reviewed_resource_mismatch(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()

        app_wrong_id = sample_approval(prop)
        app_wrong_id.reviewed_resource.resource_id = uuid4()
        with pytest.raises(AccountingError, match="APPROVAL_VERSION_MISMATCH"):
            engine.post(prop, app_wrong_id)

        app_wrong_ver = sample_approval(prop)
        app_wrong_ver.reviewed_resource.resource_version = "99"
        with pytest.raises(AccountingError, match="APPROVAL_VERSION_MISMATCH"):
            engine.post(prop, app_wrong_ver)

        app_wrong_type = sample_approval(prop)
        app_wrong_type.reviewed_resource.resource_type = "bank_transaction"
        with pytest.raises(AccountingError, match="APPROVAL_VERSION_MISMATCH"):
            engine.post(prop, app_wrong_type)

    @pytest.mark.parametrize(
        "non_approve_action",
        ["REJECT", "REQUEST_EVIDENCE", "ESCALATE"],
    )
    def test_non_approve_actions_rejected(self, non_approve_action: str) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        app = sample_approval(prop)
        app.action = non_approve_action  # type: ignore[assignment]
        with pytest.raises(AccountingError, match="APPROVAL_REQUIRED"):
            engine.post(prop, app)

    @pytest.mark.parametrize("actor_type", ["AGENT", "SERVICE"])
    def test_non_human_approvers_rejected(self, actor_type: str) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        app = sample_approval(prop)
        app.actor.actor_type = actor_type  # type: ignore[assignment]
        with pytest.raises(AccountingError, match="APPROVAL_REQUIRED"):
            engine.post(prop, app)

    def test_missing_separation_of_duties_assertion_rejected(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        app = sample_approval(prop)
        app.separation_of_duties_checked = False
        with pytest.raises(AccountingError, match="APPROVAL_REQUIRED"):
            engine.post(prop, app)

    def test_conflicting_approval_reference_on_proposal(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        app = sample_approval(prop)

        # Set proposal approval reference to a different approval decision ID
        prop.approval_decision = ResourceReference(
            resource_type="approval_decision",
            resource_id=uuid4(),
        )
        with pytest.raises(AccountingError, match="APPROVAL_REFERENCE_MISMATCH"):
            engine.post(prop, app)


# ==============================================================================
# 4. POSTING AND CONCURRENCY TESTS
# ==============================================================================


class TestPostingAndConcurrency:
    """Exact retries, conflict detection, double-post prevention, and concurrency."""

    def test_exact_retries_return_identical_entry(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        app = sample_approval(prop)

        entry1 = engine.post(prop, app)
        entry2 = engine.post(prop, app)
        assert entry1.entry_id == entry2.entry_id
        assert entry1 == entry2
        assert len(engine.general_ledger("INR")) == 1

    def test_modified_content_creates_posting_conflict(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        app = sample_approval(prop)
        engine.post(prop, app)

        prop_mutated = prop.model_copy(deep=True)
        prop_mutated.explanation = "Altered explanation after initial post"
        with pytest.raises(AccountingError, match="POSTING_CONFLICT"):
            engine.post(prop_mutated, app)

    def test_new_proposal_version_cannot_double_post_same_proposal_id(self) -> None:
        engine = standard_engine()
        prop_v1 = sample_proposal()
        app_v1 = sample_approval(prop_v1)
        engine.post(prop_v1, app_v1)

        prop_v2 = prop_v1.model_copy(update={"proposal_version": 2})
        app_v2 = sample_approval(prop_v2)

        with pytest.raises(AccountingError, match="POSTING_CONFLICT"):
            engine.post(prop_v2, app_v2)

    def test_concurrent_duplicate_submissions_produce_single_entry(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        app = sample_approval(prop)

        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(lambda _: engine.post(prop, app), range(32)))

        distinct_ids = {entry.entry_id for entry in results}
        assert len(distinct_ids) == 1
        assert len(engine.general_ledger("INR")) == 1

    def test_retry_after_period_close_returns_original_entry(self) -> None:
        engine = standard_engine()
        prop = sample_proposal(journal_date=DATE_2026_01_15)
        app = sample_approval(prop)
        entry = engine.post(prop, app)

        engine.close_period(DATE_2026_01_01, DATE_2026_01_31)

        retry_entry = engine.post(prop, app)
        assert retry_entry == entry

    def test_retry_after_reversal_returns_original_entry(self) -> None:
        engine = standard_engine()
        prop = sample_proposal(journal_date=DATE_2026_01_15)
        app = sample_approval(prop)
        entry = engine.post(prop, app)

        engine.reverse(entry.entry_id, DATE_2026_02_01, "Reversing original entry")

        retry_entry = engine.post(prop, app)
        assert retry_entry == entry
        assert len(engine.general_ledger("INR")) == 2


# ==============================================================================
# 5. REVERSAL TESTS
# ==============================================================================


class TestReversals:
    """Append-only reversals, line inversion, date boundaries, and conflict rules."""

    def test_reversal_creates_equal_and_opposite_lines(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        entry = engine.post(prop, sample_approval(prop))
        reversal = engine.reverse(entry.entry_id, DATE_2026_02_01, "Test reversal")

        assert reversal.reversal_of == entry.entry_id
        assert reversal.journal_date == DATE_2026_02_01
        assert len(reversal.lines) == len(entry.lines)

        for orig_line, rev_line in zip(entry.lines, reversal.lines, strict=True):
            assert orig_line.line_id != rev_line.line_id
            assert orig_line.account == rev_line.account
            assert orig_line.units == rev_line.units
            assert orig_line.description == rev_line.description
            assert orig_line.evidence_json == rev_line.evidence_json
            expected_direction = "CREDIT" if orig_line.direction == "DEBIT" else "DEBIT"
            assert rev_line.direction == expected_direction

    def test_original_entry_remains_completely_unchanged(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        entry = engine.post(prop, sample_approval(prop))
        orig_dict = entry.__dict__.copy()

        engine.reverse(entry.entry_id, DATE_2026_02_01, "Reason")
        assert entry.__dict__ == orig_dict

    def test_correct_balances_before_and_after_reversal_date(self) -> None:
        engine = standard_engine()
        prop = sample_proposal(amount_str="1000.00", journal_date=DATE_2026_01_15)
        entry = engine.post(prop, sample_approval(prop))

        engine.reverse(entry.entry_id, DATE_2026_02_01, "Duplicate payment")

        assert engine.account_balance("SYNTH-EXPENSE", "INR", DATE_2026_01_15) == Decimal("1000.00")
        assert engine.account_balance("SYNTH-EXPENSE", "INR", DATE_2026_01_31) == Decimal("1000.00")
        assert engine.account_balance("SYNTH-EXPENSE", "INR", DATE_2026_02_01) == Decimal("0.00")

    def test_reversing_non_existent_entry_rejected(self) -> None:
        engine = standard_engine()
        with pytest.raises(AccountingError, match="ENTRY_NOT_FOUND"):
            engine.reverse(uuid4(), DATE_2026_02_01, "Non-existent")

    def test_reversal_date_before_original_posting_rejected(self) -> None:
        engine = standard_engine()
        prop = sample_proposal(journal_date=DATE_2026_01_15)
        entry = engine.post(prop, sample_approval(prop))

        with pytest.raises(AccountingError, match="INVALID_REVERSAL"):
            engine.reverse(entry.entry_id, DATE_2026_01_14, "Backdated reversal")

    @pytest.mark.parametrize("blank_reason", ["", "   ", "\t\n"])
    def test_empty_or_whitespace_reasons_rejected(self, blank_reason: str) -> None:
        engine = standard_engine()
        prop = sample_proposal(journal_date=DATE_2026_01_15)
        entry = engine.post(prop, sample_approval(prop))

        with pytest.raises(AccountingError, match="INVALID_REVERSAL"):
            engine.reverse(entry.entry_id, DATE_2026_02_01, blank_reason)

    def test_duplicate_and_conflicting_reversal_requests(self) -> None:
        engine = standard_engine()
        prop = sample_proposal(journal_date=DATE_2026_01_15)
        entry = engine.post(prop, sample_approval(prop))

        rev1 = engine.reverse(entry.entry_id, DATE_2026_02_01, "Original reason")
        rev2 = engine.reverse(entry.entry_id, DATE_2026_02_01, "Original reason")
        assert rev1 == rev2

        with pytest.raises(AccountingError, match="REVERSAL_CONFLICT"):
            engine.reverse(entry.entry_id, DATE_2026_02_02, "Original reason")

        with pytest.raises(AccountingError, match="REVERSAL_CONFLICT"):
            engine.reverse(entry.entry_id, DATE_2026_02_01, "Changed reason")

    def test_reversal_of_a_reversal_rejected(self) -> None:
        engine = standard_engine()
        prop = sample_proposal(journal_date=DATE_2026_01_15)
        entry = engine.post(prop, sample_approval(prop))
        reversal = engine.reverse(entry.entry_id, DATE_2026_02_01, "First reversal")

        with pytest.raises(AccountingError, match="REVERSAL_OF_REVERSAL"):
            engine.reverse(reversal.entry_id, DATE_2026_02_15, "Cannot reverse reversal")

    def test_concurrent_reversals_are_thread_safe(self) -> None:
        engine = standard_engine()
        prop = sample_proposal(journal_date=DATE_2026_01_15)
        entry = engine.post(prop, sample_approval(prop))

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(
                    lambda _: engine.reverse(entry.entry_id, DATE_2026_02_01, "Concurrent test"),
                    range(16),
                )
            )

        assert len({rev.entry_id for rev in results}) == 1
        assert len(engine.general_ledger("INR")) == 2


# ==============================================================================
# 6. REPORTS & GOLDEN ACCOUNTING SCENARIOS
# ==============================================================================


class TestReportsAndGoldenScenarios:
    """Comprehensive golden accounting tests derived from accounting first principles."""

    def test_comprehensive_golden_accounting_lifecycle(self) -> None:
        engine = standard_engine()
        base_prop = sample_proposal()

        # Step 1: Capital Contribution (Debit Cash 50,000, Credit Capital 50,000)
        p1 = demo_proposal(base_prop, "AP_PAYMENT", "cap-1", "CASH", "CAPITAL")
        p1.lines[0].amount.amount = Decimal("50000.00")
        p1.lines[1].amount.amount = Decimal("50000.00")
        p1.proposed_journal_date = DATE_2026_01_05
        engine.post(p1, sample_approval(p1))

        # Step 2: AP Invoice (Debit Expense 12,000, Credit Payable 12,000)
        p2 = demo_proposal(base_prop, "AP_INVOICE", "inv-1", "EXPENSE", "PAYABLE")
        p2.lines[0].amount.amount = Decimal("12000.00")
        p2.lines[1].amount.amount = Decimal("12000.00")
        p2.proposed_journal_date = DATE_2026_01_10
        engine.post(p2, sample_approval(p2))

        # Step 3: AP Payment (Debit Payable 12,000, Credit Cash 12,000)
        p3 = demo_proposal(base_prop, "AP_PAYMENT", "pay-1", "PAYABLE", "CASH")
        p3.lines[0].amount.amount = Decimal("12000.00")
        p3.lines[1].amount.amount = Decimal("12000.00")
        p3.proposed_journal_date = DATE_2026_01_12
        engine.post(p3, sample_approval(p3))

        # Step 4: AR Invoice (Debit AR 30,000, Credit Revenue 30,000)
        p4 = demo_proposal(base_prop, "AR_INVOICE", "ar-1", "AR", "REVENUE")
        p4.lines[0].amount.amount = Decimal("30000.00")
        p4.lines[1].amount.amount = Decimal("30000.00")
        p4.proposed_journal_date = DATE_2026_01_15
        engine.post(p4, sample_approval(p4))

        # Step 5: AR Receipt (Debit Cash 20,000, Credit AR 20,000)
        p5 = demo_proposal(base_prop, "AR_RECEIPT", "rec-1", "CASH", "AR")
        p5.lines[0].amount.amount = Decimal("20000.00")
        p5.lines[1].amount.amount = Decimal("20000.00")
        p5.proposed_journal_date = DATE_2026_01_20
        engine.post(p5, sample_approval(p5))

        # Independent Account Balances Check
        # Cash: 50,000 - 12,000 + 20,000 = 58,000
        assert engine.account_balance("CASH", "INR", DATE_2026_01_31) == Decimal("58000.00")
        # AR: 30,000 - 20,000 = 10,000
        assert engine.account_balance("AR", "INR", DATE_2026_01_31) == Decimal("10000.00")
        # AP: -12,000 + 12,000 = 0
        assert engine.account_balance("PAYABLE", "INR", DATE_2026_01_31) == Decimal("0.00")
        # Capital: credit 50,000 (debit-positive balance: -50,000)
        assert engine.account_balance("CAPITAL", "INR", DATE_2026_01_31) == Decimal("-50000.00")
        # Revenue: credit 30,000 (debit-positive balance: -30,000)
        assert engine.account_balance("REVENUE", "INR", DATE_2026_01_31) == Decimal("-30000.00")
        # Expense: debit 12,000
        assert engine.account_balance("EXPENSE", "INR", DATE_2026_01_31) == Decimal("12000.00")

        # Trial Balance Check
        tb = engine.trial_balance("INR", DATE_2026_01_31)
        total_debits = sum(row.debit for row in tb)
        total_credits = sum(row.credit for row in tb)
        assert total_debits == Decimal("80000.00")
        assert total_credits == Decimal("80000.00")
        assert total_debits == total_credits

        # Profit and Loss Check
        pnl = engine.profit_and_loss("INR", DATE_2026_01_01, DATE_2026_01_31)
        assert pnl.revenue == Decimal("30000.00")
        assert pnl.expenses == Decimal("12000.00")
        assert pnl.net_income == Decimal("18000.00")

        # Balance Sheet Check
        bs = engine.balance_sheet("INR", DATE_2026_01_31)
        assert bs.assets == Decimal("68000.00")
        assert bs.liabilities == Decimal("0.00")
        assert bs.retained_earnings == Decimal("18000.00")
        assert bs.equity == Decimal("68000.00")
        assert bs.assets == bs.liabilities + bs.equity

    def test_net_loss_flows_into_equity(self) -> None:
        engine = standard_engine()
        base_prop = sample_proposal()

        p_cap = demo_proposal(base_prop, "AP_PAYMENT", "cap", "CASH", "CAPITAL")
        p_cap.lines[0].amount.amount = Decimal("20000.00")
        p_cap.lines[1].amount.amount = Decimal("20000.00")
        p_cap.proposed_journal_date = DATE_2026_01_05
        engine.post(p_cap, sample_approval(p_cap))

        p_rev = demo_proposal(base_prop, "AR_INVOICE", "rev", "AR", "REVENUE")
        p_rev.lines[0].amount.amount = Decimal("5000.00")
        p_rev.lines[1].amount.amount = Decimal("5000.00")
        p_rev.proposed_journal_date = DATE_2026_01_10
        engine.post(p_rev, sample_approval(p_rev))

        p_exp = demo_proposal(base_prop, "AP_INVOICE", "exp", "EXPENSE", "PAYABLE")
        p_exp.lines[0].amount.amount = Decimal("8000.00")
        p_exp.lines[1].amount.amount = Decimal("8000.00")
        p_exp.proposed_journal_date = DATE_2026_01_15
        engine.post(p_exp, sample_approval(p_exp))

        pnl = engine.profit_and_loss("INR", DATE_2026_01_01, DATE_2026_01_31)
        assert pnl.net_income == Decimal("-3000.00")

        bs = engine.balance_sheet("INR", DATE_2026_01_31)
        assert bs.retained_earnings == Decimal("-3000.00")
        assert bs.assets == Decimal("25000.00")
        assert bs.liabilities == Decimal("8000.00")
        assert bs.equity == Decimal("17000.00")
        assert bs.assets == bs.liabilities + bs.equity

    def test_inclusive_date_boundaries_and_invalid_ranges(self) -> None:
        engine = standard_engine()
        base = sample_proposal()

        p1 = demo_proposal(base, "AP_INVOICE", "d1", "EXPENSE", "PAYABLE")
        p1.lines[0].amount.amount = Decimal("1000.00")
        p1.lines[1].amount.amount = Decimal("1000.00")
        p1.proposed_journal_date = DATE_2026_01_10
        engine.post(p1, sample_approval(p1))

        p2 = demo_proposal(base, "AP_INVOICE", "d2", "EXPENSE", "PAYABLE")
        p2.lines[0].amount.amount = Decimal("2000.00")
        p2.lines[1].amount.amount = Decimal("2000.00")
        p2.proposed_journal_date = DATE_2026_01_20
        engine.post(p2, sample_approval(p2))

        # Single-day inclusive range: Day 1
        pnl_d1 = engine.profit_and_loss("INR", DATE_2026_01_10, DATE_2026_01_10)
        assert pnl_d1.expenses == Decimal("1000.00")

        # Range spanning both
        pnl_both = engine.profit_and_loss("INR", DATE_2026_01_10, DATE_2026_01_20)
        assert pnl_both.expenses == Decimal("3000.00")

        # Range before activity
        pnl_prior = engine.profit_and_loss("INR", DATE_2026_01_01, DATE_2026_01_09)
        assert pnl_prior.expenses == Decimal("0.00")

        # Invalid inverted range
        with pytest.raises(AccountingError, match="INVALID_DATE_RANGE"):
            engine.profit_and_loss("INR", DATE_2026_01_20, DATE_2026_01_10)

    def test_currency_isolation_between_usd_and_inr(self) -> None:
        engine = standard_engine()
        p_inr = sample_proposal(amount_str="5000.00", currency="INR")
        engine.post(p_inr, sample_approval(p_inr))

        p_usd = sample_proposal(amount_str="100.00", currency="USD")
        engine.post(p_usd, sample_approval(p_usd))

        assert len(engine.general_ledger("INR")) == 1
        assert len(engine.general_ledger("USD")) == 1

        bs_inr = engine.balance_sheet("INR", DATE_2026_01_31)
        bs_usd = engine.balance_sheet("USD", DATE_2026_01_31)
        assert bs_inr.retained_earnings == Decimal("-5000.00")
        assert bs_usd.retained_earnings == Decimal("-100.00")

    def test_multi_period_reversal_reporting_effects(self) -> None:
        engine = standard_engine()
        base = sample_proposal()

        sale = demo_proposal(base, "AR_INVOICE", "sale-1", "AR", "REVENUE")
        sale.lines[0].amount.amount = Decimal("10000.00")
        sale.lines[1].amount.amount = Decimal("10000.00")
        sale.proposed_journal_date = DATE_2026_01_15
        entry = engine.post(sale, sample_approval(sale))

        engine.reverse(entry.entry_id, DATE_2026_02_15, "Cancelled contract")

        # January P&L: Unchanged, shows $10,000 revenue
        pnl_jan = engine.profit_and_loss("INR", DATE_2026_01_01, DATE_2026_01_31)
        assert pnl_jan.revenue == Decimal("10000.00")
        assert pnl_jan.net_income == Decimal("10000.00")

        # February P&L: Shows -$10,000 revenue reversal
        pnl_feb = engine.profit_and_loss("INR", DATE_2026_02_01, DATE_2026_02_28)
        assert pnl_feb.revenue == Decimal("-10000.00")
        assert pnl_feb.net_income == Decimal("-10000.00")

        # Cumulative Balance Sheet as of Feb 28: fully cleared
        bs_feb = engine.balance_sheet("INR", DATE_2026_02_28)
        assert bs_feb.assets == Decimal("0.00")
        assert bs_feb.equity == Decimal("0.00")
        assert bs_feb.retained_earnings == Decimal("0.00")


# ==============================================================================
# 7. PERIOD CLOSE TESTS
# ==============================================================================


class TestPeriodClose:
    """Period close locks, historical stability, overlap prevention, and retries."""

    def test_close_locks_postings_and_reversals_through_period_end(self) -> None:
        engine = standard_engine()
        prop = sample_proposal(journal_date=DATE_2026_01_15)
        entry = engine.post(prop, sample_approval(prop))

        engine.close_period(DATE_2026_01_01, DATE_2026_01_31)

        # Backdated posting during closed period
        p_closed = sample_proposal(journal_date=DATE_2026_01_20)
        with pytest.raises(AccountingError, match="PERIOD_CLOSED"):
            engine.post(p_closed, sample_approval(p_closed))

        # Backdated posting prior to closed period
        p_prior = sample_proposal(journal_date=date(2025, 12, 31))
        with pytest.raises(AccountingError, match="PERIOD_CLOSED"):
            engine.post(p_prior, sample_approval(p_prior))

        # Reversal targeting a closed date
        with pytest.raises(AccountingError, match="PERIOD_CLOSED"):
            engine.reverse(entry.entry_id, date(2026, 1, 25), "Closed reversal")

        # Reversal on a later open date is permitted
        rev = engine.reverse(entry.entry_id, DATE_2026_02_01, "Open reversal")
        assert rev.journal_date == DATE_2026_02_01

    def test_later_entries_permitted_after_period_close(self) -> None:
        engine = standard_engine()
        engine.close_period(DATE_2026_01_01, DATE_2026_01_31)

        prop_later = sample_proposal(journal_date=DATE_2026_02_01)
        entry = engine.post(prop_later, sample_approval(prop_later))
        assert entry.journal_date == DATE_2026_02_01

    def test_exact_close_retries_are_stable(self) -> None:
        engine = standard_engine()
        res1 = engine.close_period(DATE_2026_01_01, DATE_2026_01_31)
        res2 = engine.close_period(DATE_2026_01_01, DATE_2026_01_31)
        assert res1 == res2

    def test_overlapping_close_periods_rejected(self) -> None:
        engine = standard_engine()
        engine.close_period(DATE_2026_01_01, DATE_2026_01_31)

        # Partial overlap
        with pytest.raises(AccountingError, match="PERIOD_OVERLAP"):
            engine.close_period(DATE_2026_01_15, DATE_2026_02_15)

        # Contained overlap
        with pytest.raises(AccountingError, match="PERIOD_OVERLAP"):
            engine.close_period(DATE_2026_01_10, DATE_2026_01_20)

    def test_adjacent_sequential_periods_succeed(self) -> None:
        engine = standard_engine()
        engine.close_period(DATE_2026_01_01, DATE_2026_01_31)
        res_feb = engine.close_period(DATE_2026_02_01, DATE_2026_02_28)
        assert len(res_feb) == len(engine._scales)

    def test_historical_close_results_remain_stable_after_later_activity(self) -> None:
        engine = standard_engine()
        p1 = sample_proposal(amount_str="1000.00", journal_date=DATE_2026_01_15)
        engine.post(p1, sample_approval(p1))

        initial_close = engine.close_period(DATE_2026_01_01, DATE_2026_01_31)

        # Later activity in February
        p2 = sample_proposal(amount_str="5000.00", journal_date=DATE_2026_02_15)
        engine.post(p2, sample_approval(p2))

        # Re-querying January close
        requeried_close = engine.close_period(DATE_2026_01_01, DATE_2026_01_31)
        assert initial_close == requeried_close

    def test_close_on_empty_ledger_and_multiple_currencies(self) -> None:
        engine = standard_engine({"USD": 2, "EUR": 2, "JPY": 0})
        close_res = engine.close_period(DATE_2026_01_01, DATE_2026_01_31)

        assert len(close_res) == 3
        currencies = [c.currency for c in close_res]
        assert currencies == ["EUR", "JPY", "USD"]

        for item in close_res:
            assert item.profit_and_loss.net_income == Decimal("0")
            assert item.balance_sheet.assets == Decimal("0")


# ==============================================================================
# 8. DEMO TEMPLATES AND SNAPSHOT IMMUTABILITY TESTS
# ==============================================================================


class TestDemoTemplatesAndSnapshots:
    """Deterministic proposal templates, immutable snapshots, and mapping."""

    @pytest.mark.parametrize(
        "template_name,expected_debit,expected_credit",
        [
            ("AP_INVOICE", "EXPENSE", "PAYABLE"),
            ("AP_PAYMENT", "PAYABLE", "CASH"),
            ("AR_INVOICE", "AR", "REVENUE"),
            ("AR_RECEIPT", "CASH", "AR"),
        ],
    )
    def test_template_account_mapping(
        self, template_name: str, expected_debit: str, expected_credit: str
    ) -> None:
        source = sample_proposal()
        prop = demo_proposal(
            source,
            template_name,  # type: ignore[arg-type]
            "doc-key-1",
            expected_debit,
            expected_credit,
        )
        assert prop.lines[0].direction == "DEBIT"
        assert prop.lines[0].account_reference == expected_debit
        assert prop.lines[1].direction == "CREDIT"
        assert prop.lines[1].account_reference == expected_credit
        assert prop.approval_decision is None
        assert prop.policy_decision is None
        assert prop.posting_status == "UNPOSTED"
        assert prop.accounting_validation == "NOT_VALIDATED"

    def test_deterministic_output_and_distinct_keys(self) -> None:
        source = sample_proposal()
        p1 = demo_proposal(source, "AP_INVOICE", "inv-1", "EXPENSE", "PAYABLE")
        p2 = demo_proposal(source, "AP_INVOICE", "inv-1", "EXPENSE", "PAYABLE")
        p3 = demo_proposal(source, "AP_INVOICE", "inv-2", "EXPENSE", "PAYABLE")
        p4 = demo_proposal(source, "AR_INVOICE", "inv-1", "AR", "REVENUE")

        assert p1 == p2
        assert p1.proposal_id != p3.proposal_id
        assert p1.proposal_id != p4.proposal_id

    def test_evidence_and_correlation_preserved_in_template(self) -> None:
        source = sample_proposal()
        prop = demo_proposal(source, "AP_INVOICE", "inv-1", "EXPENSE", "PAYABLE")

        assert prop.correlation == source.correlation
        assert prop.source_evidence == source.source_evidence
        assert prop.lines[0].source_evidence == source.lines[0].source_evidence

    def test_invalid_template_inputs_raise_value_error(self) -> None:
        source = sample_proposal()

        with pytest.raises(ValueError, match="UNKNOWN_TEMPLATE"):
            demo_proposal(source, "INVALID_TEMPLATE", "k", "EXPENSE", "PAYABLE")  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="INVALID_TEMPLATE_INPUT"):
            demo_proposal(source, "AP_INVOICE", "   ", "EXPENSE", "PAYABLE")

        with pytest.raises(ValueError, match="INVALID_TEMPLATE_INPUT"):
            demo_proposal(source, "AP_INVOICE", "k", "EXPENSE", "EXPENSE")

    def test_source_mutations_cannot_alter_posted_snapshots(self) -> None:
        engine = standard_engine()
        prop = sample_proposal()
        app = sample_approval(prop)
        entry = engine.post(prop, app)

        original_explanation = prop.explanation
        original_line_desc = prop.lines[0].description

        prop.explanation = "Mutated after posting"
        prop.lines[0].description = "Mutated line"

        assert entry.lines[0].description == original_line_desc
        stored_source = json.loads(entry.source_json)
        assert stored_source["explanation"] == original_explanation
        assert stored_source["lines"][0]["description"] == original_line_desc
