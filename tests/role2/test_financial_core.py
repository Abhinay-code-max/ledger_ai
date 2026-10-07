"""Golden accounting scenarios and adversarial Role 2 boundary checks."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import uuid4

import pytest

from financial_core import Account, AccountingError, FinancialEngine
from financial_core.money import decimal_amount, minor_units
from financial_core.templates import demo_proposal
from ledgerai_contracts.v1.approvals import ApprovalDecision
from ledgerai_contracts.v1.journals import JournalProposal

FIXTURES = Path(__file__).resolve().parents[2] / "shared/fixtures/contracts/v1"
JAN = date(2026, 1, 15)
FEB = date(2026, 2, 1)


def proposal() -> JournalProposal:
    return JournalProposal.model_validate_json(
        (FIXTURES / "journal-proposal.unposted.json").read_text()
    )


def approved(source: JournalProposal) -> ApprovalDecision:
    payload = json.loads((FIXTURES / "approval-decision.approved.json").read_text())
    payload["reviewed_resource"]["resource_id"] = str(source.proposal_id)
    payload["reviewed_resource"]["resource_version"] = str(source.proposal_version)
    return ApprovalDecision.model_validate(payload)


def engine() -> FinancialEngine:
    return FinancialEngine(
        proposal().tenant_context,
        [
            Account("SYNTH-EXPENSE", "Expense", "EXPENSE"),
            Account("SYNTH-PAYABLE", "Payable", "LIABILITY"),
            Account("CASH", "Cash", "ASSET"),
            Account("AR", "Receivable", "ASSET"),
            Account("SALES", "Sales", "REVENUE"),
            Account("CAPITAL", "Capital", "EQUITY"),
            Account("INACTIVE", "Inactive", "ASSET", False),
        ],
        {"INR": 2, "USD": 2, "JPY": 0, "KWD": 3},
    )


def test_fixture_post_balances_and_snapshot() -> None:
    ledger, source = engine(), proposal()
    decision = approved(source)
    entry = ledger.post(source, decision)
    assert entry == ledger.post(source, decision)
    assert ledger.account_balance("SYNTH-EXPENSE", "INR", JAN) == Decimal("1250.00")
    assert ledger.account_balance("SYNTH-PAYABLE", "INR", JAN) == Decimal("-1250.00")
    assert len(ledger.general_ledger("INR")) == 1
    assert source.posting_status == "UNPOSTED"
    assert source.accounting_validation == "NOT_VALIDATED"
    source.lines[0].description = "changed after posting"
    assert entry.lines[0].description == "Synthetic expense"
    assert json.loads(entry.source_json)["lines"][0]["description"] == "Synthetic expense"
    with pytest.raises(FrozenInstanceError):
        entry.currency = "USD"  # type: ignore[misc]


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("account_reference", "UNKNOWN", "ACCOUNT_UNAVAILABLE"),
        ("account_reference", "INACTIVE", "ACCOUNT_UNAVAILABLE"),
    ],
)
def test_account_validation(field: str, value: str, code: str) -> None:
    payload = proposal().model_dump(mode="json")
    payload["lines"][0][field] = value
    ledger = engine()
    with pytest.raises(AccountingError, match=code):
        ledger.post(JournalProposal.model_validate(payload), approved(proposal()))
    assert ledger.general_ledger("INR") == ()


@pytest.mark.parametrize(
    "case,code",
    [
        ("unbalanced", "UNBALANCED_JOURNAL"),
        ("precision", "CURRENCY_PRECISION"),
        ("currency", "CURRENCY_MISMATCH"),
        ("duplicate", "DUPLICATE_LINE"),
        ("evidence", "EVIDENCE_UNRESOLVABLE"),
        ("tenant", "TENANT_MISMATCH"),
        ("unsupported", "UNSUPPORTED_CURRENCY"),
    ],
)
def test_reject_bad_proposals(case: str, code: str) -> None:
    payload = proposal().model_dump(mode="json")
    if case == "unbalanced":
        payload["lines"][0]["amount"]["amount"] = "1250.01"
    elif case == "precision":
        for line in payload["lines"]:
            line["amount"]["amount"] = "1250.001"
    elif case == "currency":
        payload["lines"][0]["amount"]["currency"] = "USD"
    elif case == "duplicate":
        payload["lines"][1]["line_id"] = payload["lines"][0]["line_id"]
    elif case == "evidence":
        payload["lines"][0]["source_evidence"] = [{}]
    elif case == "tenant":
        payload["tenant_context"]["organization_id"] = str(uuid4())
    else:
        payload["currency"] = "ZZZ"
    ledger = engine()
    with pytest.raises(AccountingError, match=code):
        ledger.validate_proposal(JournalProposal.model_validate(payload))
    assert ledger.general_ledger("INR") == ()


@pytest.mark.parametrize(
    "case,code",
    [
        ("version", "APPROVAL_VERSION_MISMATCH"),
        ("resource", "APPROVAL_VERSION_MISMATCH"),
        ("type", "APPROVAL_VERSION_MISMATCH"),
        ("rejected", "APPROVAL_REQUIRED"),
        ("duties", "APPROVAL_REQUIRED"),
        ("actor", "APPROVAL_REQUIRED"),
        ("tenant", "TENANT_MISMATCH"),
    ],
)
def test_approval_binding(case: str, code: str) -> None:
    source = proposal()
    payload = approved(source).model_dump(mode="json")
    if case == "version":
        payload["reviewed_resource"]["resource_version"] = "2"
    elif case == "resource":
        payload["reviewed_resource"]["resource_id"] = str(uuid4())
    elif case == "type":
        payload["reviewed_resource"]["resource_type"] = "invoice"
    elif case == "rejected":
        payload["action"] = "REJECT"
    elif case == "duties":
        payload["separation_of_duties_checked"] = False
    elif case == "actor":
        payload["actor"]["actor_type"] = "AGENT"
    else:
        payload["tenant_context"]["tenant_id"] = str(uuid4())
    ledger = engine()
    with pytest.raises(AccountingError, match=code):
        ledger.post(source, ApprovalDecision.model_validate(payload))
    assert ledger.general_ledger("INR") == ()


def test_conflicting_version_and_content_cannot_double_post() -> None:
    ledger, source = engine(), proposal()
    ledger.post(source, approved(source))
    source.proposal_version = 2
    with pytest.raises(AccountingError, match="POSTING_CONFLICT"):
        ledger.post(source, approved(source))
    source.proposal_version = 1
    source.lines[0].description = "mutated"
    with pytest.raises(AccountingError, match="POSTING_CONFLICT"):
        ledger.post(source, approved(source))
    assert len(ledger.general_ledger("INR")) == 1


def test_concurrent_post_is_idempotent() -> None:
    ledger, source = engine(), proposal()
    decision = approved(source)
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: ledger.post(source, decision).entry_id, range(32)))
    assert len(set(ids)) == 1
    assert len(ledger.general_ledger("INR")) == 1


def test_reversal_append_only_and_as_of() -> None:
    ledger, source = engine(), proposal()
    entry = ledger.post(source, approved(source))
    reversal = ledger.reverse(entry.entry_id, FEB, "duplicate invoice")
    assert reversal == ledger.reverse(entry.entry_id, FEB, "duplicate invoice")
    assert reversal.reversal_of == entry.entry_id
    assert ledger.account_balance("SYNTH-EXPENSE", "INR", JAN) == Decimal("1250")
    assert ledger.account_balance("SYNTH-EXPENSE", "INR", FEB) == 0
    assert len(ledger.general_ledger("INR")) == 2
    with pytest.raises(AccountingError, match="REVERSAL_CONFLICT"):
        ledger.reverse(entry.entry_id, FEB, "different reason")
    with pytest.raises(AccountingError, match="REVERSAL_OF_REVERSAL"):
        ledger.reverse(reversal.entry_id, FEB, "again")


@pytest.mark.parametrize(
    "amount,scale,expected",
    [
        ("0.01", 2, 1),
        ("12.000", 2, 1200),
        ("5", 0, 5),
        ("1.234", 3, 1234),
        ("123456789012345678901234567890.12", 2, 12345678901234567890123456789012),
    ],
)
def test_money_is_exact_under_low_decimal_precision(amount: str, scale: int, expected: int) -> None:
    with localcontext() as context:
        context.prec = 2
        assert minor_units(amount, scale) == expected
        assert decimal_amount(expected, scale) == Decimal(amount)


@pytest.mark.parametrize("amount", ["0", "-1", "1e2", "01", "1,000", "NaN", "Infinity"])
def test_money_rejects_invalid_strings(amount: str) -> None:
    with pytest.raises(AccountingError, match="INVALID_MONEY"):
        minor_units(amount, 2)


@pytest.mark.parametrize("amount", [1, 1.2, True])
def test_money_rejects_numbers(amount: object) -> None:
    with pytest.raises(AccountingError, match="INVALID_MONEY"):
        minor_units(amount, 2)  # type: ignore[arg-type]


def test_golden_ap_ar_statements_and_templates() -> None:
    ledger, source = engine(), proposal()
    pairs = [
        ("AP_INVOICE", "SYNTH-EXPENSE", "SYNTH-PAYABLE"),
        ("AP_PAYMENT", "SYNTH-PAYABLE", "CASH"),
        ("AR_INVOICE", "AR", "SALES"),
        ("AR_RECEIPT", "CASH", "AR"),
    ]
    for name, debit, credit in pairs:
        item = demo_proposal(source, name, "doc-1", debit, credit)  # type: ignore[arg-type]
        assert item == demo_proposal(source, name, "doc-1", debit, credit)  # type: ignore[arg-type]
        ledger.post(item, approved(item))
    pnl = ledger.profit_and_loss("INR", date(2026, 1, 1), JAN)
    assert (pnl.revenue, pnl.expenses, pnl.net_income) == (
        Decimal("1250"),
        Decimal("1250"),
        Decimal("0"),
    )
    assert ledger.account_balance("CASH", "INR", JAN) == 0
    assert ledger.account_balance("AR", "INR", JAN) == 0
    assert ledger.account_balance("SYNTH-PAYABLE", "INR", JAN) == 0
    rows = ledger.trial_balance("INR", JAN)
    assert sum(row.debit for row in rows) == sum(row.credit for row in rows)
    sheet = ledger.balance_sheet("INR", JAN)
    assert sheet.assets == sheet.liabilities + sheet.equity
    assert len(ledger.general_ledger("USD")) == 0


def test_profit_flows_into_equity() -> None:
    ledger, source = engine(), proposal()
    sale = demo_proposal(source, "AR_INVOICE", "sale", "AR", "SALES")
    ledger.post(sale, approved(sale))
    sheet = ledger.balance_sheet("INR", JAN)
    assert sheet.assets == sheet.equity == sheet.retained_earnings == Decimal("1250")
    assert sheet.liabilities == 0


def test_close_locks_posting_and_allows_later_reversal() -> None:
    ledger, source = engine(), proposal()
    entry = ledger.post(source, approved(source))
    closed = ledger.close_period(date(2026, 1, 1), date(2026, 1, 31))
    assert closed == ledger.close_period(date(2026, 1, 1), date(2026, 1, 31))
    assert ledger.post(source, approved(source)) == entry
    new_source = demo_proposal(source, "AP_INVOICE", "new", "SYNTH-EXPENSE", "SYNTH-PAYABLE")
    with pytest.raises(AccountingError, match="PERIOD_CLOSED"):
        ledger.post(new_source, approved(new_source))
    with pytest.raises(AccountingError, match="PERIOD_CLOSED"):
        ledger.reverse(entry.entry_id, JAN, "closed")
    ledger.reverse(entry.entry_id, FEB, "next period")
    assert closed == ledger.close_period(date(2026, 1, 1), date(2026, 1, 31))
    with pytest.raises(AccountingError, match="PERIOD_OVERLAP"):
        ledger.close_period(JAN, FEB)


def test_invalid_report_ranges_and_missing_accounts() -> None:
    ledger = engine()
    with pytest.raises(AccountingError, match="INVALID_DATE_RANGE"):
        ledger.profit_and_loss("INR", FEB, JAN)
    with pytest.raises(AccountingError, match="ACCOUNT_UNAVAILABLE"):
        ledger.account_balance("missing", "INR", JAN)
    with pytest.raises(AccountingError, match="ENTRY_NOT_FOUND"):
        ledger.reverse(uuid4(), JAN, "missing")


def test_approval_reference_mismatch() -> None:
    payload = proposal().model_dump(mode="json")
    payload["approval_decision"] = {
        "resource_type": "approval_decision",
        "resource_id": str(uuid4()),
    }
    source = JournalProposal.model_validate(payload)
    with pytest.raises(AccountingError, match="APPROVAL_REFERENCE_MISMATCH"):
        engine().post(source, approved(source))


def test_closed_books_reject_earlier_backdating() -> None:
    ledger, source = engine(), proposal()
    ledger.close_period(date(2026, 1, 1), date(2026, 1, 31))
    source.proposed_journal_date = date(2025, 12, 31)
    with pytest.raises(AccountingError, match="PERIOD_CLOSED"):
        ledger.post(source, approved(source))


def test_large_balanced_journal_does_not_round() -> None:
    ledger = engine()
    payload = proposal().model_dump(mode="json")
    for line in payload["lines"]:
        line["amount"]["amount"] = "123456789012345678901234567890.12"
    source = JournalProposal.model_validate(payload)
    with localcontext() as context:
        context.prec = 2
        ledger.post(source, approved(source))
        assert ledger.account_balance("SYNTH-EXPENSE", "INR", JAN) == Decimal(
            "123456789012345678901234567890.12"
        )


@pytest.mark.parametrize(
    "currency,amount,units",
    [
        ("JPY", "1250", 1250),
        ("KWD", "1250.123", 1250123),
        ("USD", "1250.12", 125012),
    ],
)
def test_currency_scales_and_reporting_isolation(currency: str, amount: str, units: int) -> None:
    ledger = engine()
    payload = proposal().model_dump(mode="json")
    payload["currency"] = currency
    for line in payload["lines"]:
        line["amount"] = {"currency": currency, "amount": amount}
    source = JournalProposal.model_validate(payload)
    entry = ledger.post(source, approved(source))
    assert entry.lines[0].units == units
    assert ledger.general_ledger("INR") == ()
    assert ledger.account_balance("SYNTH-EXPENSE", currency, JAN) == Decimal(amount)


def test_mutated_contract_is_revalidated() -> None:
    source = proposal()
    source.lines.clear()
    with pytest.raises(ValueError):
        engine().post(source, approved(source))


def test_duplicate_chart_accounts_rejected() -> None:
    account = Account("CASH", "Cash", "ASSET")
    with pytest.raises(AccountingError, match="DUPLICATE_ACCOUNT"):
        FinancialEngine(proposal().tenant_context, [account, account], {"INR": 2})


def test_canonical_account_code_is_valid() -> None:
    assert Account("CASH", "Cash", "ASSET").code == "CASH"


@pytest.mark.parametrize("code", [" CASH", "CASH ", " CASH ", "", " ", "\t", "\nCASH", "CASH\n"])
def test_account_codes_reject_whitespace(code: str) -> None:
    with pytest.raises(AccountingError) as caught:
        Account(code, "Cash", "ASSET")
    assert caught.value.code == "INVALID_ACCOUNT"


def test_unknown_template_uses_accounting_error() -> None:
    with pytest.raises(AccountingError) as caught:
        demo_proposal(proposal(), "UNKNOWN", "doc-1", "CASH", "AR")  # type: ignore[arg-type]
    assert caught.value.code == "UNKNOWN_TEMPLATE"


@pytest.mark.parametrize(
    "key,debit,credit", [("", "CASH", "AR"), (" ", "CASH", "AR"), ("doc-1", "CASH", "CASH")]
)
def test_invalid_template_input_uses_accounting_error(key: str, debit: str, credit: str) -> None:
    with pytest.raises(AccountingError) as caught:
        demo_proposal(proposal(), "AR_RECEIPT", key, debit, credit)
    assert caught.value.code == "INVALID_TEMPLATE_INPUT"
