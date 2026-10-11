"""Synthetic NOVA golden ledger definition and reproducible expected financial outputs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid5

from ledgerai_contracts.v1.common import ProvenanceReference
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role2.domain.models import (
    Account,
    AccountType,
    Direction,
    DomainJournalLine,
    NormalBalance,
)

NOVA_NAMESPACE = UUID("15c191c2-81d1-4f79-8a38-7d8543649c71")


def nova_id(name: str) -> UUID:
    return uuid5(NOVA_NAMESPACE, name)


NOVA_TENANT = nova_id("nova:tenant")
NOVA_ORG = nova_id("nova:organization")
NOVA_ENTITY = nova_id("nova:legal-entity")

NOVA_TENANT_CONTEXT = EntityTenantContext(
    tenant_id=NOVA_TENANT,
    organization_id=NOVA_ORG,
    legal_entity_id=NOVA_ENTITY,
)

NOVA_PERIOD_ID = nova_id("nova:period:2026-01")
NOVA_PERIOD_START = date(2026, 1, 1)
NOVA_PERIOD_END = date(2026, 1, 31)

NOVA_ACCOUNTS: list[Account] = [
    Account.create(
        "1010", "Cash and Cash Equivalents", AccountType.ASSET, "INR", NormalBalance.DEBIT
    ),
    Account.create("1020", "Accounts Receivable", AccountType.ASSET, "INR", NormalBalance.DEBIT),
    Account.create("1030", "Prepaid Expenses", AccountType.ASSET, "INR", NormalBalance.DEBIT),
    Account.create(
        "1040", "GST Input Tax Credit Receivable", AccountType.ASSET, "INR", NormalBalance.DEBIT
    ),
    Account.create(
        "1510", "Computer Equipment and Hardware", AccountType.ASSET, "INR", NormalBalance.DEBIT
    ),
    Account.create("2010", "Accounts Payable", AccountType.LIABILITY, "INR", NormalBalance.CREDIT),
    Account.create(
        "2030", "GST Output Tax Payable", AccountType.LIABILITY, "INR", NormalBalance.CREDIT
    ),
    Account.create("2040", "TDS Payable", AccountType.LIABILITY, "INR", NormalBalance.CREDIT),
    Account.create(
        "3010", "Common Stock / Share Capital", AccountType.EQUITY, "INR", NormalBalance.CREDIT
    ),
    Account.create("3020", "Retained Earnings", AccountType.EQUITY, "INR", NormalBalance.CREDIT),
    Account.create(
        "4010",
        "Cloud Engineering Services Revenue",
        AccountType.REVENUE,
        "INR",
        NormalBalance.CREDIT,
    ),
    Account.create(
        "4020",
        "SaaS Platform Subscription Revenue",
        AccountType.REVENUE,
        "INR",
        NormalBalance.CREDIT,
    ),
    Account.create(
        "5010",
        "Cloud Infrastructure Hosting Expense",
        AccountType.EXPENSE,
        "INR",
        NormalBalance.DEBIT,
    ),
    Account.create(
        "5020", "Developer Tooling Expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT
    ),
    Account.create(
        "5030", "Engineering Salaries Expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT
    ),
    Account.create(
        "5040", "Legal and Advisory Expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT
    ),
]


def evidence(doc_name: str, page: int = 1) -> list[ProvenanceReference]:
    return [
        ProvenanceReference(
            source_document_id=nova_id(f"doc:{doc_name}"),
            document_version="1",
            page_number=page,
            evidence_hash="a" * 64,
        )
    ]


def nova_line(
    code: str,
    direction: Direction,
    amount_str: str,
    desc: str,
    doc_ref: str,
) -> DomainJournalLine:
    return DomainJournalLine(
        line_id=nova_id(f"line:{code}:{desc}:{amount_str}"),
        account_reference=code,
        direction=direction,
        amount=Decimal(amount_str),
        currency="INR",
        description=desc,
        source_evidence=evidence(doc_ref),
    )


# Golden Transaction Lines
OPENING_BALANCE_LINES = [
    nova_line(
        "1010", Direction.DEBIT, "5000000.00", "Opening bank balance", "bank_statement_2026_01"
    ),
    nova_line(
        "1510", Direction.DEBIT, "1500000.00", "Opening hardware assets", "asset_register_2025"
    ),
    nova_line(
        "3010", Direction.CREDIT, "5000000.00", "Share capital investment", "incorporation_filing"
    ),
    nova_line(
        "3020",
        Direction.CREDIT,
        "1500000.00",
        "Cumulative retained earnings",
        "audited_fy25_report",
    ),
]

INVOICE_BILLING_LINES = [
    nova_line(
        "1020", Direction.DEBIT, "1180000.00", "Client invoice receivable", "inv_nova_2026_001"
    ),
    nova_line(
        "4010", Direction.CREDIT, "1000000.00", "Cloud architecture consulting", "inv_nova_2026_001"
    ),
    nova_line("2030", Direction.CREDIT, "180000.00", "GST Output 18%", "inv_nova_2026_001"),
]

HOSTING_EXPENSE_LINES = [
    nova_line("5010", Direction.DEBIT, "200000.00", "AWS Cloud hosting", "bill_aws_jan2026"),
    nova_line("1040", Direction.DEBIT, "36000.00", "GST Input credit 18%", "bill_aws_jan2026"),
    nova_line("2010", Direction.CREDIT, "236000.00", "AWS Accounts payable", "bill_aws_jan2026"),
]

PAYMENT_COLLECTION_LINES = [
    nova_line("1010", Direction.DEBIT, "1180000.00", "Client wire receipt", "bank_wire_recv_101"),
    nova_line(
        "1020", Direction.CREDIT, "1180000.00", "Clear receivable INV-001", "bank_wire_recv_101"
    ),
]

TOOLING_EXPENSE_LINES = [
    nova_line("5020", Direction.DEBIT, "50000.00", "Developer IDE licenses", "bill_jetbrains_01"),
    nova_line("2010", Direction.CREDIT, "50000.00", "Tooling payable", "bill_jetbrains_01"),
]

ERRONEOUS_LEGAL_LINES = [
    nova_line(
        "5040", Direction.DEBIT, "75000.00", "Erroneous legal advisory charge", "draft_bill_law_01"
    ),
    nova_line("2010", Direction.CREDIT, "75000.00", "Erroneous legal payable", "draft_bill_law_01"),
]

REPLACEMENT_LEGAL_LINES = [
    nova_line(
        "5040", Direction.DEBIT, "40000.00", "Correct legal advisory retainer", "final_bill_law_01"
    ),
    nova_line("2040", Direction.CREDIT, "4000.00", "TDS 10% withholding", "final_bill_law_01"),
    nova_line(
        "2010", Direction.CREDIT, "36000.00", "Net payable to legal counsel", "final_bill_law_01"
    ),
]

VENDOR_PAYOUT_LINES = [
    nova_line(
        "2010", Direction.DEBIT, "236000.00", "AWS Vendor invoice payment", "bank_wire_sent_201"
    ),
    nova_line("1010", Direction.CREDIT, "236000.00", "Bank payout to AWS", "bank_wire_sent_201"),
]

# Exact expected balances down to the penny (INR)
EXPECTED_NOVA_FIGURES = {
    "total_debits": Decimal("7770000.00"),
    "total_credits": Decimal("7770000.00"),
    "total_revenue": Decimal("1000000.00"),
    "total_expenses": Decimal("290000.00"),
    "net_income": Decimal("710000.00"),
    "total_assets": Decimal("748000.00"),  # Wait: 5,944,000 + 36,000 + 1,500,000 = 7,480,000.00
    "total_liabilities": Decimal("270000.00"),
    "total_equity": Decimal("7210000.00"),  # 6,500,000 + 710,000 = 7,210,000.00
}
EXPECTED_NOVA_FIGURES["total_assets"] = Decimal("7480000.00")
