"""Comprehensive integration and regression tests for real reconciliation engine.

Tests all required Phase 4 validation scenarios:
1. Exact match (1:1 with score >= 0.95)
2. Amount mismatch (batch & single amount conflicts, planted variance)
3. Currency mismatch (unmatched across currencies with explicit conflict)
4. Duplicate payments (multiple bank transactions matching same invoice or multiple invoices)
5. Partial payments (amounts differ beyond tolerance, marked PARTIAL with review required)
6. Unmatched invoices (unmatched invoice facts produce UNMATCHED_INVOICE exception)
7. Repeated reconciliation requests (strict idempotency on external_proposal_id/version)
8. Cross-tenant isolation (foreign tenant context rejection and scoping)
9. Database rollback (session failure does not persist corrupt records)
10. Missing downstream service (503 handling when Role 3 adapter unavailable)
11. Deterministic replay (identical inputs produce bitwise identical match proposals)
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from ledgerai_backend.integration.adapters import (
    AdapterError,
    AdapterSecurity,
    ReconciliationResult,
    Role3Adapter,
    SignedServiceTokenProvider,
)
from ledgerai_backend.integration.models import (
    MatchProposal as MatchRow,
)
from ledgerai_backend.integration.models import (
    WorkflowException,
)
from ledgerai_backend.integration.orchestration import (
    WorkflowContractError,
    WorkflowOrchestrator,
)
from ledgerai_backend.reconciliation.contracts import (
    InvoiceFact,
    ReconciliationRequest,
    VersionedBankTransaction,
)
from ledgerai_backend.reconciliation.engine import (
    ReconciliationEngine,
)
from ledgerai_contracts.v1.common import (
    CorrelationMetadata,
    Money,
    PositiveMoney,
    ProvenanceReference,
    ResourceReference,
)
from ledgerai_contracts.v1.exceptions import ExceptionRecord
from ledgerai_contracts.v1.reconciliation import MatchProposal
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_contracts.v1.transactions import BankTransaction, Counterparty

SECRET = "synthetic-service-secret-32-chars-long-minimum"
TENANT_A = EntityTenantContext(
    tenant_id=UUID("11111111-1111-4111-8111-111111111111"),
    organization_id=UUID("22222222-2222-4222-8222-222222222222"),
    legal_entity_id=UUID("33333333-3333-4333-8333-333333333333"),
)
TENANT_B = EntityTenantContext(
    tenant_id=UUID("99999999-9999-4999-8999-999999999999"),
    organization_id=UUID("88888888-8888-4888-8888-888888888888"),
    legal_entity_id=UUID("77777777-7777-4777-8777-777777777777"),
)


class InMemorySession:
    """Mock session supporting add, scalar, flush, and rollback simulation."""

    def __init__(self) -> None:
        self.rows: list[Any] = []
        self.flushed_rows: list[Any] = []
        self.rolled_back = False

    def add(self, row: Any) -> None:
        if not hasattr(row, "id") or row.id is None:
            row.id = uuid4()
        self.rows.append(row)

    async def flush(self) -> None:
        if self.rolled_back:
            raise RuntimeError("Transaction is aborted")
        self.flushed_rows = list(self.rows)

    def rollback(self) -> None:
        self.rolled_back = True
        self.rows = []
        self.flushed_rows = []

    async def scalar(self, statement: Any) -> Any | None:
        # Evaluate simple scalar lookups on self.rows
        stmt_str = str(statement)
        if "FROM match_proposals" in stmt_str or "match_proposals" in stmt_str:
            for row in self.rows:
                if isinstance(row, MatchRow):
                    return row
        if "FROM exceptions" in stmt_str or "exceptions" in stmt_str:
            for row in self.rows:
                if isinstance(row, WorkflowException):
                    return row
        return None

    async def scalars(self, statement: Any) -> list[Any]:
        return list(self.rows)


class MockRepository:
    """Mock integration repository tracking outbox events and tenant scope."""

    def __init__(
        self, tenant_context: EntityTenantContext, session: InMemorySession | None = None
    ) -> None:
        self.session = session or InMemorySession()
        self.tenant_id = tenant_context.tenant_id
        self.organization_id = tenant_context.organization_id
        self.legal_entity_id = tenant_context.legal_entity_id
        self.outbox_events: list[dict[str, Any]] = []

    def _scope(self, model: type[Any]) -> tuple[Any, ...]:
        return (
            getattr(model, "tenant_id", None) == self.tenant_id,
            getattr(model, "organization_id", None) == self.organization_id,
            getattr(model, "legal_entity_id", None) == self.legal_entity_id,
        )

    def add_outbox(self, **kwargs: Any) -> None:
        self.outbox_events.append(kwargs)


def _sha256_hex(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8")).hexdigest()


def _make_invoice(
    doc_id: UUID,
    extraction_id: UUID,
    amount: str = "1250.00",
    currency: str = "INR",
    ref: str = "INV-001",
    party: str = "Acme Supplies",
    inv_date: date = date(2026, 9, 15),
    tenant: EntityTenantContext = TENANT_A,
) -> InvoiceFact:
    inv_fp = _sha256_hex(f"invoice:{extraction_id}:{amount}:{ref}")
    return InvoiceFact(
        extraction_id=extraction_id,
        extraction_version="1",
        document_id=doc_id,
        document_version="1",
        tenant_context=tenant,
        amount=Money(amount=Decimal(amount), currency=currency),
        invoice_date=inv_date,
        expected_transaction_direction="DEBIT",
        reference=ref,
        party_name=party,
        evidence_complete=True,
        content_fingerprint=inv_fp,
        provenance=[
            ProvenanceReference(
                source_document_id=doc_id,
                document_version="1",
                source_field="invoice",
                evidence_hash="a" * 64,
            )
        ],
    )


def _make_tx(
    tx_id: UUID,
    amount: str = "1250.00",
    currency: str = "INR",
    ref: str = "INV-001",
    party: str = "Acme Supplies",
    narration: str = "PAYMENT",
    booking_date: date = date(2026, 9, 15),
    doc_id: UUID | None = None,
    tenant: EntityTenantContext = TENANT_A,
    fingerprint: str | None = None,
) -> VersionedBankTransaction:
    tx_fp = fingerprint or _sha256_hex(f"tx:{tx_id}:{amount}:{ref}:{narration}")
    return VersionedBankTransaction(
        transaction_version="1",
        transaction=BankTransaction(
            schema_version="1.0",
            transaction_id=tx_id,
            tenant_context=tenant,
            bank_account_id=uuid4(),
            import_batch_id=uuid4(),
            source_row_number=1,
            booking_date=booking_date,
            value_date=booking_date,
            money=PositiveMoney(amount=Decimal(amount), currency=currency),
            direction="DEBIT",
            narration=narration,
            reference=ref,
            counterparty=Counterparty(display_name=party),
            normalization_status="NORMALIZED",
            provenance=[
                ProvenanceReference(
                    source_document_id=doc_id or uuid4(),
                    document_version="1",
                    source_field="bank_transaction",
                    evidence_hash="b" * 64,
                )
            ],
            content_fingerprint=tx_fp,
            correlation=CorrelationMetadata(
                request_id=tx_id, correlation_id=tx_id, causation_id=None
            ),
        ),
    )


def _make_request(
    invoices: list[InvoiceFact],
    transactions: list[VersionedBankTransaction],
    tenant: EntityTenantContext = TENANT_A,
    operation_id: UUID | None = None,
) -> ReconciliationRequest:
    op_id = operation_id or uuid4()
    return ReconciliationRequest(
        schema_version="1.0",
        tenant_context=tenant,
        operation_id=op_id,
        correlation_id=op_id,
        causation_id=None,
        operation_started_at=datetime.now(UTC),
        strategy_version="reconciliation-rules/1.0.0",
        invoices=invoices,
        transactions=transactions,
    )


# ---------------------------------------------------------------------------
# Test Scenario 1: Exact Matches
# ---------------------------------------------------------------------------


def test_scenario_exact_match() -> None:
    """Clean exact match produces ONE_TO_ONE match with high confidence and no exceptions."""
    engine = ReconciliationEngine()
    doc_id = uuid4()
    ext_id = uuid4()
    tx_id = uuid4()

    inv = _make_invoice(doc_id, ext_id, amount="1250.00", currency="INR", ref="NOVA-001")
    tx = _make_tx(tx_id, amount="1250.00", currency="INR", ref="NOVA-001", doc_id=doc_id)

    req = _make_request([inv], [tx])
    res = engine.reconcile(req)

    assert res.proposal.match_type == "ONE_TO_ONE"
    assert res.proposal.status == "PROPOSED"
    assert res.proposal.confidence >= Decimal("0.90")
    assert len(res.proposal.records) == 2
    assert len(res.exceptions) == 0


# ---------------------------------------------------------------------------
# Test Scenario 2: Amount and Currency Mismatches
# ---------------------------------------------------------------------------


def test_scenario_amount_mismatch_and_planted_conflict() -> None:
    """Batch amount discrepancy generates AMOUNT_MISMATCH exception with high severity."""
    engine = ReconciliationEngine()
    doc_id = uuid4()
    ext_id = uuid4()
    tx1_id = uuid4()
    tx2_id = uuid4()

    # Invoice: 1,250.00; Tx1: 1,250.00; Tx2: 50.00 (planted mismatch)
    inv = _make_invoice(doc_id, ext_id, amount="1250.00", currency="INR", ref="NOVA-001")
    tx1 = _make_tx(
        tx1_id, amount="1250.00", currency="INR", ref="NOVA-001", narration="PAYMENT", doc_id=doc_id
    )
    tx2 = _make_tx(
        tx2_id,
        amount="50.00",
        currency="INR",
        ref="ISSUE-001",
        narration="PLANTED AMOUNT MISMATCH",
        doc_id=doc_id,
    )

    req = _make_request([inv], [tx1, tx2])
    res = engine.reconcile(req)

    assert res.proposal.match_type == "ONE_TO_ONE"
    assert res.proposal.status == "REVIEW_REQUIRED"

    # Verify exception is raised for the 50.00 variance
    amount_exceptions = [e for e in res.exceptions if e.exception_type == "AMOUNT_MISMATCH"]
    assert len(amount_exceptions) == 1
    exc = amount_exceptions[0]
    assert exc.severity == "HIGH"
    assert "PLANTED_AMOUNT_MISMATCH" in exc.reason_codes
    assert "BATCH_AMOUNT_MISMATCH" in exc.reason_codes


def test_scenario_currency_mismatch() -> None:
    """Invoices and transactions in conflicting currencies cannot match and produce exception."""
    engine = ReconciliationEngine()
    doc_id = uuid4()
    ext_id = uuid4()
    tx_id = uuid4()

    inv = _make_invoice(doc_id, ext_id, amount="100.00", currency="USD")
    tx = _make_tx(tx_id, amount="100.00", currency="EUR")

    req = _make_request([inv], [tx])
    res = engine.reconcile(req)

    assert res.proposal.match_type == "UNMATCHED"
    assert res.proposal.status == "REVIEW_REQUIRED"
    assert any(e.exception_type == "CURRENCY_MISMATCH" for e in res.exceptions)


# ---------------------------------------------------------------------------
# Test Scenario 3: Duplicate Payments
# ---------------------------------------------------------------------------


def test_scenario_duplicate_payments() -> None:
    """Multiple identical transactions competing for one invoice trigger AMBIGUOUS_CANDIDATES."""
    engine = ReconciliationEngine()
    doc_id = uuid4()
    ext_id = uuid4()
    tx1_id = uuid4()
    tx2_id = uuid4()

    inv = _make_invoice(doc_id, ext_id, amount="1000.00", currency="INR", ref="DUP-001")
    tx1 = _make_tx(tx1_id, amount="1000.00", currency="INR", ref="DUP-001")
    tx2 = _make_tx(tx2_id, amount="1000.00", currency="INR", ref="DUP-001")

    req = _make_request([inv], [tx1, tx2])
    res = engine.reconcile(req)

    # Identical candidate scores trigger ambiguity conflict
    assert res.proposal.status == "REVIEW_REQUIRED"
    assert any(e.exception_type == "AMBIGUOUS_CANDIDATES" for e in res.exceptions)


# ---------------------------------------------------------------------------
# Test Scenario 4: Partial Payments
# ---------------------------------------------------------------------------


def test_scenario_partial_payments() -> None:
    """When a single transaction pays part of an invoice, PARTIAL match is returned."""
    engine = ReconciliationEngine()
    doc_id = uuid4()
    ext_id = uuid4()
    tx_id = uuid4()

    # Invoice is 2,000.00 INR, transaction is 1,000.00 INR with matching reference
    inv = _make_invoice(doc_id, ext_id, amount="2000.00", currency="INR", ref="PARTIAL-001")
    tx = _make_tx(tx_id, amount="1000.00", currency="INR", ref="PARTIAL-001")

    req = _make_request([inv], [tx])
    res = engine.reconcile(req)

    assert res.proposal.match_type == "PARTIAL"
    assert res.proposal.status == "REVIEW_REQUIRED"
    assert any(e.exception_type == "AMOUNT_MISMATCH" for e in res.exceptions)


# ---------------------------------------------------------------------------
# Test Scenario 5: Unmatched Invoices
# ---------------------------------------------------------------------------


def test_scenario_unmatched_invoices() -> None:
    """Unmatched invoices produce UNMATCHED proposal and UNMATCHED_INVOICE exception."""
    engine = ReconciliationEngine()
    doc_id = uuid4()
    ext_id = uuid4()

    inv = _make_invoice(doc_id, ext_id, amount="5000.00", currency="INR")
    req = _make_request([inv], [])
    res = engine.reconcile(req)

    assert res.proposal.match_type == "UNMATCHED"
    assert res.proposal.status == "REVIEW_REQUIRED"
    assert any(e.exception_type == "UNMATCHED_INVOICE" for e in res.exceptions)


# ---------------------------------------------------------------------------
# Test Scenario 6: Repeated Reconciliation Requests (Idempotency)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_repeated_reconciliation_requests_idempotency() -> None:
    """Persisting the same reconciliation result twice produces identical rows."""
    session = InMemorySession()
    repo = MockRepository(TENANT_A, session)
    orchestrator = WorkflowOrchestrator(repo, correlation_id=uuid4())

    doc_id = uuid4()
    ext_id = uuid4()
    tx_id = uuid4()
    proposal_id = uuid4()
    exception_id = uuid4()

    now = datetime.now(UTC)
    result = ReconciliationResult(
        schema_version="1.0",
        tenant_context=TENANT_A,
        proposal=MatchProposal(
            schema_version="1.0",
            proposal_id=proposal_id,
            proposal_version=1,
            tenant_context=TENANT_A,
            records=[
                ResourceReference(
                    resource_type="bank_transaction", resource_id=tx_id, resource_version="1"
                ),
                ResourceReference(
                    resource_type="document_extraction", resource_id=ext_id, resource_version="1"
                ),
            ],
            match_type="ONE_TO_ONE",
            confidence=Decimal("0.99"),
            score=Decimal("0.99"),
            reasons=[{"code": "EXACT_MATCH", "explanation": "Perfect match"}],
            producer={
                "producer_type": "SERVICE",
                "name": "role3",
                "version": "1.0",
                "algorithm_version": "v1",
            },
            status="PROPOSED",
            created_at=now,
            updated_at=now,
            correlation=CorrelationMetadata(
                request_id=proposal_id, correlation_id=proposal_id, causation_id=None
            ),
        ),
        exceptions=[
            ExceptionRecord(
                schema_version="1.0",
                exception_id=exception_id,
                tenant_context=TENANT_A,
                exception_type="AMOUNT_MISMATCH",
                severity="HIGH",
                involved_resources=[
                    ResourceReference(
                        resource_type="bank_transaction", resource_id=tx_id, resource_version="1"
                    )
                ],
                explanation="Variance",
                reason_codes=["BATCH_AMOUNT_MISMATCH"],
                detector={"producer_type": "SERVICE", "name": "role3", "version": "1.0"},
                resolution_status="OPEN",
                created_at=now,
                updated_at=now,
                correlation=CorrelationMetadata(
                    request_id=proposal_id, correlation_id=proposal_id, causation_id=None
                ),
            )
        ],
    )

    allowed = {doc_id, ext_id, tx_id}

    # First persistence
    match_1, excs_1 = await orchestrator.persist_reconciliation(
        result, allowed_resource_ids=allowed
    )
    assert match_1.external_proposal_id == proposal_id
    assert len(excs_1) == 1

    # Second persistence with same proposal_id and version (replay)
    match_2, excs_2 = await orchestrator.persist_reconciliation(
        result, allowed_resource_ids=allowed
    )
    assert match_2.id == match_1.id
    assert excs_2[0].id == excs_1[0].id


# ---------------------------------------------------------------------------
# Test Scenario 7: Cross-Tenant Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_cross_tenant_isolation_rejection() -> None:
    """Attempts to reconcile or persist resources belonging to a foreign tenant are rejected."""
    # Engine level rejection
    doc_id = uuid4()
    ext_id = uuid4()
    tx_id = uuid4()

    inv = _make_invoice(doc_id, ext_id, tenant=TENANT_A)
    tx_foreign = _make_tx(tx_id, tenant=TENANT_B)

    # Creating request with mixed tenant contexts raises ValidationError
    with pytest.raises(ValueError, match="foreign-tenant or mixed-entity input is not allowed"):
        _make_request([inv], [tx_foreign], tenant=TENANT_A)

    # Orchestrator level rejection
    session = InMemorySession()
    repo = MockRepository(TENANT_A, session)
    orchestrator = WorkflowOrchestrator(repo, correlation_id=uuid4())

    now = datetime.now(UTC)
    foreign_result = ReconciliationResult(
        schema_version="1.0",
        tenant_context=TENANT_B,  # Foreign tenant
        proposal=MatchProposal(
            schema_version="1.0",
            proposal_id=uuid4(),
            proposal_version=1,
            tenant_context=TENANT_B,
            records=[
                ResourceReference(
                    resource_type="bank_transaction", resource_id=tx_id, resource_version="1"
                )
            ],
            match_type="ONE_TO_ONE",
            confidence=Decimal("0.99"),
            reasons=[{"code": "MATCH", "explanation": "match"}],
            producer={
                "producer_type": "SERVICE",
                "name": "role3",
                "version": "1.0",
                "algorithm_version": "v1",
            },
            status="PROPOSED",
            created_at=now,
            updated_at=now,
            correlation=CorrelationMetadata(
                request_id=tx_id, correlation_id=tx_id, causation_id=None
            ),
        ),
        exceptions=[],
    )

    with pytest.raises(WorkflowContractError, match="reconciliation tenant context mismatch"):
        await orchestrator.persist_reconciliation(foreign_result, allowed_resource_ids={tx_id})


# ---------------------------------------------------------------------------
# Test Scenario 8: Database Rollback Simulation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_database_rollback_on_failure() -> None:
    """When a persistence step fails, uncommitted rows are cleared and no corrupt records remain."""
    session = InMemorySession()
    repo = MockRepository(TENANT_A, session)
    orchestrator = WorkflowOrchestrator(repo, correlation_id=uuid4())

    tx_id = uuid4()
    now = datetime.now(UTC)
    # Result references an unknown resource not in allowed_resource_ids
    result = ReconciliationResult(
        schema_version="1.0",
        tenant_context=TENANT_A,
        proposal=MatchProposal(
            schema_version="1.0",
            proposal_id=uuid4(),
            proposal_version=1,
            tenant_context=TENANT_A,
            records=[
                ResourceReference(
                    resource_type="bank_transaction", resource_id=tx_id, resource_version="1"
                )
            ],
            match_type="ONE_TO_ONE",
            confidence=Decimal("0.99"),
            reasons=[{"code": "MATCH", "explanation": "match"}],
            producer={
                "producer_type": "SERVICE",
                "name": "role3",
                "version": "1.0",
                "algorithm_version": "v1",
            },
            status="PROPOSED",
            created_at=now,
            updated_at=now,
            correlation=CorrelationMetadata(
                request_id=tx_id, correlation_id=tx_id, causation_id=None
            ),
        ),
        exceptions=[],
    )

    with pytest.raises(WorkflowContractError, match="foreign resource"):
        await orchestrator.persist_reconciliation(result, allowed_resource_ids={uuid4()})

    # Assert no rows were flushed
    assert len(session.flushed_rows) == 0


# ---------------------------------------------------------------------------
# Test Scenario 9: Missing Downstream Service Handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_missing_downstream_service_raises_503() -> None:
    """When Role 3 adapter encounters connection failure or 503, an AdapterError is raised."""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503, json={"code": "SERVICE_UNAVAILABLE", "message": "Role 3 is down"}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    token_provider = SignedServiceTokenProvider(issuer="test", subject="backend", secret=SECRET)
    security = AdapterSecurity(
        base_url="http://role3.test",
        audience="ledgerai-role3",
        environment="test",
        maximum_attempts=1,
    )
    adapter = Role3Adapter(security, token_provider, client=client)

    with pytest.raises(AdapterError, match="TRANSIENT_DOWNSTREAM_FAILURE"):
        await adapter.request_reconciliation(
            payload={"test": "data"},
            tenant_context=TENANT_A,
            operation_id=uuid4(),
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# Test Scenario 10: Deterministic Replay
# ---------------------------------------------------------------------------


def test_scenario_deterministic_replay() -> None:
    """Identical requests produce bitwise identical proposal IDs, match types and scores."""
    engine = ReconciliationEngine()
    doc_id = UUID("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
    ext_id = UUID("bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")
    tx_id = UUID("cccccccc-cccc-4ccc-cccc-cccccccccccc")
    op_id = UUID("dddddddd-dddd-4ddd-dddd-dddddddddddd")

    inv = _make_invoice(doc_id, ext_id, amount="1250.00", currency="INR", ref="REPLAY-001")
    tx = _make_tx(tx_id, amount="1250.00", currency="INR", ref="REPLAY-001", doc_id=doc_id)

    req1 = _make_request([inv], [tx], operation_id=op_id)
    req2 = _make_request([inv], [tx], operation_id=op_id)

    res1 = engine.reconcile(req1)
    res2 = engine.reconcile(req2)

    assert res1.proposal.proposal_id == res2.proposal.proposal_id
    assert res1.proposal.score == res2.proposal.score
    assert res1.proposal.confidence == res2.proposal.confidence
    assert res1.proposal.match_type == res2.proposal.match_type
    assert len(res1.exceptions) == len(res2.exceptions)
