"""Tests for strict multi-tenant isolation and database-level boundaries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from ledgerai_contracts.v1.common import ProvenanceReference
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role2.database.in_memory import InMemoryRole2Repository
from ledgerai_role2.domain.models import (
    Account,
    AccountType,
    Direction,
    DomainJournalLine,
    NormalBalance,
    PeriodStatus,
)
from ledgerai_role2.service import Role2Service

TENANT_A = EntityTenantContext(
    tenant_id=UUID("11111111-1111-4000-8000-000000000001"),
    organization_id=UUID("11111111-1111-4000-8000-000000000002"),
    legal_entity_id=UUID("11111111-1111-4000-8000-000000000003"),
)

TENANT_B = EntityTenantContext(
    tenant_id=UUID("22222222-2222-4000-8000-000000000001"),
    organization_id=UUID("22222222-2222-4000-8000-000000000002"),
    legal_entity_id=UUID("22222222-2222-4000-8000-000000000003"),
)


@pytest.mark.asyncio
async def test_tenant_data_is_completely_isolated() -> None:
    shared_store = {
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
    repo_a = InMemoryRole2Repository(TENANT_A, shared_store=shared_store)
    repo_b = InMemoryRole2Repository(TENANT_B, shared_store=shared_store)

    service_a = Role2Service(repo_a)

    # 1. Setup Tenant A
    await repo_a.save_account(
        Account.create("1010", "Cash A", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    await repo_a.save_account(
        Account.create("4010", "Sales A", AccountType.REVENUE, "INR", NormalBalance.CREDIT)
    )
    period_a = uuid4()
    await repo_a.save_period(
        period_id=period_a,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        state=PeriodStatus.OPEN,
    )

    # 2. Setup Tenant B
    await repo_b.save_account(
        Account.create("1010", "Cash B", AccountType.ASSET, "USD", NormalBalance.DEBIT)
    )
    await repo_b.save_account(
        Account.create("4010", "Sales B", AccountType.REVENUE, "USD", NormalBalance.CREDIT)
    )
    period_b = uuid4()
    await repo_b.save_period(
        period_id=period_b,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        state=PeriodStatus.OPEN,
    )

    # Verify Account Isolation
    acc_a = await repo_a.get_account("1010")
    acc_b = await repo_b.get_account("1010")
    assert acc_a is not None and acc_b is not None
    assert acc_a.account_name == "Cash A"
    assert acc_b.account_name == "Cash B"
    assert acc_a.currency == "INR"
    assert acc_b.currency == "USD"

    # Post a journal in Tenant A
    ev = [
        ProvenanceReference(
            source_document_id=uuid4(), document_version="1", evidence_hash="0" * 64
        )
    ]
    post_a = await service_a.post_journal(
        operation_id=uuid4(),
        proposal_id=uuid4(),
        proposal_version=1,
        accounting_period_id=period_a,
        raw_payload={"tenant": "A"},
        inline_lines=[
            DomainJournalLine(
                uuid4(), "1010", Direction.DEBIT, Decimal("500.00"), "INR", source_evidence=ev
            ),
            DomainJournalLine(
                uuid4(), "4010", Direction.CREDIT, Decimal("500.00"), "INR", source_evidence=ev
            ),
        ],
        journal_date=date(2026, 1, 15),
        currency="INR",
    )
    assert post_a.outcome == "POSTED"
    j_id_a = UUID(post_a.posted_journal_id)

    # Tenant B should NOT see Tenant A's journal
    j_from_b = await repo_b.get_journal(j_id_a)
    assert j_from_b is None

    # Tenant B's journals list must be empty
    journals_b = await repo_b.list_domain_journals_for_period(period_b)
    assert len(journals_b) == 0

    # Tenant A's journals list must contain exactly 1 journal
    journals_a = await repo_a.list_domain_journals_for_period(period_a)
    assert len(journals_a) == 1
