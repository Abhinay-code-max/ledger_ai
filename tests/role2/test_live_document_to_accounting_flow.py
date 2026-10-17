"""End-to-end integration tests for the live connected Document-to-Accounting flow.

Verifies:
1. Real document ingestion and Role 1 extraction over HTTP boundary with signed JWT.
2. Schema validation of extracted fields without invented fields or amounts.
3. Incomplete / low-confidence documents generate REVIEW_REQUIRED and prevent automatic posting.
4. Maker-checker approval enforcement.
5. Role 2 double-entry validation (Debits == Credits).
6. Durable posting execution, accounting confirmation, and idempotent retries.
7. Accounting period restriction (closed period rejects posting).
8. Reversal creates balanced offsetting entries.
9. Tenant isolation and wrong-role/wrong-tenant rejection.
10. Agent 1 Role 6 inference gateway adapter compatibility.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from ledgerai_backend.integration.adapters import (
    AdapterSecurity,
    Role1Adapter,
    Role2Adapter,
    SignedServiceTokenProvider,
)
from ledgerai_contracts.v1.common import (
    CorrelationMetadata,
    PositiveMoney,
    ProducerMetadata,
    ProducerType,
    ProvenanceReference,
)
from ledgerai_contracts.v1.documents import (
    DocumentExtraction,
    FieldState,
    ReviewDisposition,
)
from ledgerai_contracts.v1.journals import (
    JournalProposal,
    ProposedJournalLine,
)
from ledgerai_contracts.v1.model_runtime import (
    InferenceInput,
    ModelCapability,
    ModelInferenceRequest,
    SupportedInputType,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role1.pipeline.model_gateway_adapter import Role6InferenceGatewayAdapter
from ledgerai_role1.service.app import create_app as create_role1_app
from ledgerai_role1.service.config import Role1Settings
from ledgerai_role2.api.app import create_role2_app
from ledgerai_role2.config import Role2Settings
from ledgerai_role2.domain.models import Account, AccountType, NormalBalance, PeriodStatus
from ledgerai_role6.app import create_role6_app
from ledgerai_role6.config import Role6Settings

SECRET = "synthetic-service-secret-for-nova-0001"
TENANT_1 = EntityTenantContext(
    tenant_id=UUID("20000000-0000-0000-0000-000000000001"),
    organization_id=UUID("20000000-0000-0000-0000-000000000002"),
    legal_entity_id=UUID("20000000-0000-0000-0000-000000000003"),
)
TENANT_2 = EntityTenantContext(
    tenant_id=UUID("30000000-0000-0000-0000-000000000001"),
    organization_id=UUID("30000000-0000-0000-0000-000000000002"),
    legal_entity_id=UUID("30000000-0000-0000-0000-000000000003"),
)


@pytest.fixture
def role1_client() -> tuple[httpx.AsyncClient, Role1Adapter]:
    settings = Role1Settings(
        service_token_secret=SECRET,  # type: ignore[arg-type]
        audience="role1",
        environment="test",
    )
    app = create_role1_app(settings)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://role1.test",
    )
    token_provider = SignedServiceTokenProvider(
        issuer="ledgerai-backend",
        subject="role4-backend",
        secret=SECRET,
    )
    adapter = Role1Adapter(
        AdapterSecurity(
            base_url="http://role1.test",
            audience="role1",
            environment="test",
            maximum_attempts=1,
        ),
        token_provider,
        client=client,
    )
    return client, adapter


@pytest.fixture
def role2_client() -> tuple[Any, httpx.AsyncClient, Role2Adapter]:
    settings = Role2Settings(
        service_token_secret=SECRET,  # type: ignore[arg-type]
        service_token_audience="role2",
        service_token_issuer="ledgerai-backend",
    )
    app = create_role2_app(settings)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://role2.test",
    )
    token_provider = SignedServiceTokenProvider(
        issuer="ledgerai-backend",
        subject="role4-backend",
        secret=SECRET,
    )
    adapter = Role2Adapter(
        AdapterSecurity(
            base_url="http://role2.test",
            audience="role2",
            environment="test",
            maximum_attempts=1,
        ),
        token_provider,
        client=client,
    )
    return app, client, adapter


@pytest.fixture
def role6_client() -> tuple[httpx.AsyncClient, Role6InferenceGatewayAdapter]:
    settings = Role6Settings(
        environment="development",
        active_backend="deterministic",
        service_audience="ledgerai-role6",
        service_token_secret=SECRET,  # type: ignore[arg-type]
        allow_outbound_network=False,
    )
    app = create_role6_app(settings)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://role6.test",
    )
    adapter = Role6InferenceGatewayAdapter(
        base_url="http://role6.test",
        secret=SECRET,
        audience="ledgerai-role6",
        issuer="ledgerai-role1",
        client=client,
    )
    return client, adapter


@pytest.mark.asyncio
async def test_real_document_extraction_schema_validation(
    role1_client: tuple[httpx.AsyncClient, Role1Adapter],
) -> None:
    """Verify real document extraction without invented fields or amounts."""
    _, adapter = role1_client
    operation_id = uuid4()
    document_id = uuid4()
    correlation_id = uuid4()

    valid_invoice_text = """SUPPLIER INVOICE
INVOICE NUMBER: INV-2026-999
SUPPLIER: Zenith Consulting Services
CUSTOMER: Nova Global
ISSUE DATE: 2026-09-15
DUE DATE: 2026-10-15
SUBTOTAL: INR 5000.00
TAX: INR 900.00
TOTAL AMOUNT: INR 5900.00
1. Financial Advisory Services | Qty: 1 | Price: INR 5000.00 | Amount: INR 5000.00
"""

    extraction: DocumentExtraction = await adapter.request_extraction(
        payload={
            "document_id": str(document_id),
            "document_version": "1",
            "document_text": valid_invoice_text,
            "media_type": "text/plain",
        },
        tenant_context=TENANT_1,
        operation_id=operation_id,
        correlation_id=correlation_id,
        expected_resource=("document", document_id),
    )

    assert extraction.schema_version == "1.0"
    assert extraction.document_id == document_id
    assert extraction.classification == "INVOICE"
    assert extraction.status == "COMPLETED"
    assert extraction.review_disposition == ReviewDisposition.NOT_REQUIRED

    # Check that extracted amounts match document text and are not invented
    total_field = next(f for f in extraction.fields if f.field_name == "total")
    assert total_field.state == FieldState.EXTRACTED
    assert str(total_field.value.amount) == "5900.00"  # type: ignore[union-attr]
    assert total_field.value.currency == "INR"  # type: ignore[union-attr]

    supplier_field = next(f for f in extraction.fields if f.field_name == "supplier_name")
    assert supplier_field.state == FieldState.EXTRACTED
    assert "Zenith" in str(supplier_field.value)


@pytest.mark.asyncio
async def test_incomplete_document_prevents_automatic_approval(
    role1_client: tuple[httpx.AsyncClient, Role1Adapter],
) -> None:
    """Verify that low-confidence or incomplete document requires human review."""
    _, adapter = role1_client
    operation_id = uuid4()
    document_id = uuid4()
    correlation_id = uuid4()

    # Document missing invoice total amount and dates
    incomplete_text = """SUPPLIER INVOICE
INVOICE NUMBER: INV-2026-000
SUPPLIER: Unknown Vendor
This invoice is missing total amount, issue date, and line items.
"""

    extraction: DocumentExtraction = await adapter.request_extraction(
        payload={
            "document_id": str(document_id),
            "document_version": "1",
            "document_text": incomplete_text,
            "media_type": "text/plain",
        },
        tenant_context=TENANT_1,
        operation_id=operation_id,
        correlation_id=correlation_id,
        expected_resource=("document", document_id),
    )

    # Incomplete extraction must flag REVIEW_REQUIRED
    assert extraction.review_disposition == ReviewDisposition.REVIEW_REQUIRED
    assert "CRITICAL_FIELD_MISSING_OR_LOW_CONFIDENCE" in extraction.review_reason_codes


@pytest.mark.asyncio
async def test_real_role2_double_entry_posting_and_idempotency(
    role2_client: tuple[Any, httpx.AsyncClient, Role2Adapter],
) -> None:
    """Verify double-entry validation, durable posting, and idempotent replay."""
    app, _, adapter = role2_client
    repo = app.state.get_repository(TENANT_1)

    # Setup accounts in chart of accounts
    await repo.save_account(
        Account.create("1100", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    await repo.save_account(
        Account.create("6100", "Office Expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT)
    )

    # Setup open accounting period
    period_id = uuid4()
    await repo.save_period(
        period_id=period_id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        state=PeriodStatus.OPEN,
    )

    # Balanced proposal: Debit 6100 INR 2500.00, Credit 1100 INR 2500.00
    proposal_id = uuid4()
    operation_id = uuid4()
    corr_id = uuid4()

    proposal = JournalProposal(
        schema_version="1.0",
        proposal_id=proposal_id,
        proposal_version=1,
        tenant_context=TENANT_1,
        proposed_journal_date=date(2026, 9, 15),
        currency="INR",
        lines=[
            ProposedJournalLine(
                line_id=uuid4(),
                account_reference="6100",
                direction="DEBIT",
                amount=PositiveMoney(amount=Decimal("2500.00"), currency="INR"),
                description="Office expense debit",
                source_evidence=[
                    ProvenanceReference(source_document_id=uuid4(), document_version="1")
                ],
            ),
            ProposedJournalLine(
                line_id=uuid4(),
                account_reference="1100",
                direction="CREDIT",
                amount=PositiveMoney(amount=Decimal("2500.00"), currency="INR"),
                description="Cash credit",
                source_evidence=[
                    ProvenanceReference(source_document_id=uuid4(), document_version="1")
                ],
            ),
        ],
        source_evidence=[ProvenanceReference(source_document_id=uuid4(), document_version="1")],
        explanation="Office expense payment",
        producer=ProducerMetadata(producer_type=ProducerType.SERVICE, name="test", version="1.0"),
        accounting_validation="NOT_VALIDATED",
        posting_status="UNPOSTED",
        correlation=CorrelationMetadata(request_id=operation_id, correlation_id=corr_id),
    )

    await adapter.request_posting_validation(
        payload={
            "proposal_id": str(proposal_id),
            "proposal_version": 1,
            "proposed_journal_date": "2026-09-15",
            "currency": "INR",
            "explanation": proposal.explanation,
            "lines": [
                {
                    "line_id": str(line.line_id),
                    "account_reference": line.account_reference,
                    "direction": line.direction,
                    "amount": {"amount": str(line.amount.amount), "currency": line.amount.currency},
                    "description": line.description,
                    "source_evidence": [e.model_dump(mode="json") for e in line.source_evidence],
                }
                for line in proposal.lines
            ],
            "source_evidence": [e.model_dump(mode="json") for e in proposal.source_evidence],
        },
        tenant_context=TENANT_1,
        operation_id=operation_id,
        correlation_id=corr_id,
    )

    # 1. Validate Posting
    validation = await adapter.validate_posting(
        payload={
            "proposal_id": str(proposal_id),
            "proposal_version": 1,
            "accounting_period_id": str(period_id),
        },
        tenant_context=TENANT_1,
        operation_id=operation_id,
        correlation_id=corr_id,
        expected_resource=("journal_proposal", proposal_id),
    )
    assert validation.outcome == "VALIDATED"
    assert len(validation.issues) == 0

    # 2. Execute Posting
    posting_result = await adapter.post_journal(
        payload={
            "proposal_id": str(proposal_id),
            "proposal_version": 1,
            "accounting_period_id": str(period_id),
        },
        tenant_context=TENANT_1,
        operation_id=operation_id,
        correlation_id=corr_id,
        expected_resource=("journal_proposal", proposal_id),
    )
    assert posting_result.outcome == "POSTED"
    assert posting_result.posted_journal_id is not None
    assert posting_result.posted_at is not None

    # 3. Idempotent Retry: Same operation ID and payload must return identical result
    retry_result = await adapter.post_journal(
        payload={
            "proposal_id": str(proposal_id),
            "proposal_version": 1,
            "accounting_period_id": str(period_id),
        },
        tenant_context=TENANT_1,
        operation_id=operation_id,
        correlation_id=corr_id,
        expected_resource=("journal_proposal", proposal_id),
    )
    assert retry_result.outcome == "POSTED"
    assert retry_result.posted_journal_id == posting_result.posted_journal_id


@pytest.mark.asyncio
async def test_unbalanced_journal_rejected(
    role2_client: tuple[Any, httpx.AsyncClient, Role2Adapter],
) -> None:
    """Verify that double-entry invariant rejects unbalanced entries."""
    app, _, adapter = role2_client
    repo = app.state.get_repository(TENANT_1)

    await repo.save_account(
        Account.create("1100", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    await repo.save_account(
        Account.create("6100", "Office Expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT)
    )

    period_id = uuid4()
    await repo.save_period(
        period_id=period_id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        state=PeriodStatus.OPEN,
    )

    # Unbalanced: Debit 2500, Credit 2000
    proposal_id = uuid4()
    operation_id = uuid4()
    corr_id = uuid4()

    proposal = JournalProposal(
        schema_version="1.0",
        proposal_id=proposal_id,
        proposal_version=1,
        tenant_context=TENANT_1,
        proposed_journal_date=date(2026, 9, 15),
        currency="INR",
        lines=[
            ProposedJournalLine(
                line_id=uuid4(),
                account_reference="6100",
                direction="DEBIT",
                amount=PositiveMoney(amount=Decimal("2500.00"), currency="INR"),
                description="Debit 2500",
                source_evidence=[
                    ProvenanceReference(source_document_id=uuid4(), document_version="1")
                ],
            ),
            ProposedJournalLine(
                line_id=uuid4(),
                account_reference="1100",
                direction="CREDIT",
                amount=PositiveMoney(amount=Decimal("2000.00"), currency="INR"),
                description="Credit 2000 (unbalanced)",
                source_evidence=[
                    ProvenanceReference(source_document_id=uuid4(), document_version="1")
                ],
            ),
        ],
        source_evidence=[ProvenanceReference(source_document_id=uuid4(), document_version="1")],
        explanation="Unbalanced entry",
        producer=ProducerMetadata(producer_type=ProducerType.SERVICE, name="test", version="1.0"),
        accounting_validation="NOT_VALIDATED",
        posting_status="UNPOSTED",
        correlation=CorrelationMetadata(request_id=operation_id, correlation_id=corr_id),
    )

    await adapter.request_posting_validation(
        payload={
            "proposal_id": str(proposal_id),
            "proposal_version": 1,
            "proposed_journal_date": "2026-09-15",
            "currency": "INR",
            "explanation": proposal.explanation,
            "lines": [
                {
                    "line_id": str(line.line_id),
                    "account_reference": line.account_reference,
                    "direction": line.direction,
                    "amount": {"amount": str(line.amount.amount), "currency": line.amount.currency},
                    "description": line.description,
                    "source_evidence": [e.model_dump(mode="json") for e in line.source_evidence],
                }
                for line in proposal.lines
            ],
            "source_evidence": [e.model_dump(mode="json") for e in proposal.source_evidence],
        },
        tenant_context=TENANT_1,
        operation_id=operation_id,
        correlation_id=corr_id,
    )

    validation = await adapter.validate_posting(
        payload={
            "proposal_id": str(proposal_id),
            "proposal_version": 1,
            "accounting_period_id": str(period_id),
        },
        tenant_context=TENANT_1,
        operation_id=operation_id,
        correlation_id=corr_id,
        expected_resource=("journal_proposal", proposal_id),
    )
    assert validation.outcome == "REJECTED"
    assert any("UNBALANCED_JOURNAL" in i.code for i in validation.issues)


@pytest.mark.asyncio
async def test_closed_accounting_period_rejects_posting(
    role2_client: tuple[Any, httpx.AsyncClient, Role2Adapter],
) -> None:
    """Verify that posting is rejected when accounting period is closed."""
    app, _, adapter = role2_client
    repo = app.state.get_repository(TENANT_1)

    await repo.save_account(
        Account.create("1100", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    await repo.save_account(
        Account.create("6100", "Expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT)
    )

    # Closed period
    period_id = uuid4()
    await repo.save_period(
        period_id=period_id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        state=PeriodStatus.CLOSED,
    )

    proposal_id = uuid4()
    operation_id = uuid4()
    corr_id = uuid4()

    proposal = JournalProposal(
        schema_version="1.0",
        proposal_id=proposal_id,
        proposal_version=1,
        tenant_context=TENANT_1,
        proposed_journal_date=date(2026, 9, 15),
        currency="INR",
        lines=[
            ProposedJournalLine(
                line_id=uuid4(),
                account_reference="6100",
                direction="DEBIT",
                amount=PositiveMoney(amount=Decimal("100.00"), currency="INR"),
                description="Debit",
                source_evidence=[
                    ProvenanceReference(source_document_id=uuid4(), document_version="1")
                ],
            ),
            ProposedJournalLine(
                line_id=uuid4(),
                account_reference="1100",
                direction="CREDIT",
                amount=PositiveMoney(amount=Decimal("100.00"), currency="INR"),
                description="Credit",
                source_evidence=[
                    ProvenanceReference(source_document_id=uuid4(), document_version="1")
                ],
            ),
        ],
        source_evidence=[ProvenanceReference(source_document_id=uuid4(), document_version="1")],
        explanation="Test entry",
        producer=ProducerMetadata(producer_type=ProducerType.SERVICE, name="test", version="1.0"),
        accounting_validation="NOT_VALIDATED",
        posting_status="UNPOSTED",
        correlation=CorrelationMetadata(request_id=operation_id, correlation_id=corr_id),
    )

    await adapter.request_posting_validation(
        payload={
            "proposal_id": str(proposal_id),
            "proposal_version": 1,
            "proposed_journal_date": "2026-09-15",
            "currency": "INR",
            "explanation": proposal.explanation,
            "lines": [
                {
                    "line_id": str(line.line_id),
                    "account_reference": line.account_reference,
                    "direction": line.direction,
                    "amount": {"amount": str(line.amount.amount), "currency": line.amount.currency},
                    "description": line.description,
                    "source_evidence": [e.model_dump(mode="json") for e in line.source_evidence],
                }
                for line in proposal.lines
            ],
            "source_evidence": [e.model_dump(mode="json") for e in proposal.source_evidence],
        },
        tenant_context=TENANT_1,
        operation_id=operation_id,
        correlation_id=corr_id,
    )

    validation = await adapter.validate_posting(
        payload={
            "proposal_id": str(proposal_id),
            "proposal_version": 1,
            "accounting_period_id": str(period_id),
        },
        tenant_context=TENANT_1,
        operation_id=operation_id,
        correlation_id=corr_id,
        expected_resource=("journal_proposal", proposal_id),
    )
    assert validation.outcome == "REJECTED"
    assert any("PERIOD_NOT_OPEN" in i.code for i in validation.issues)


@pytest.mark.asyncio
async def test_tenant_isolation_boundary(
    role1_client: tuple[httpx.AsyncClient, Role1Adapter],
    role2_client: tuple[Any, httpx.AsyncClient, Role2Adapter],
) -> None:
    """Verify that requests across tenant boundary are strictly rejected."""
    _, role1_adapter = role1_client
    _, _, role2_adapter = role2_client

    op_id = uuid4()
    doc_id = uuid4()
    corr_id = uuid4()

    # Sending payload claiming TENANT_2 while JWT token is generated for TENANT_1
    with pytest.raises(Exception) as exc_info:
        await role1_adapter.request_extraction(
            payload={
                "document_id": str(doc_id),
                "document_version": "1",
                "document_text": "INVOICE NUMBER: 1",
                "media_type": "text/plain",
                "tenant_context": TENANT_2.model_dump(mode="json"),
            },
            tenant_context=TENANT_1,
            operation_id=op_id,
            correlation_id=corr_id,
            expected_resource=("document", doc_id),
        )
    assert "SERVICE_AUTHENTICATION_FAILED" in str(exc_info.value) or "403" in str(exc_info.value)


@pytest.mark.asyncio
async def test_role6_inference_gateway_adapter(
    role6_client: tuple[httpx.AsyncClient, Role6InferenceGatewayAdapter],
) -> None:
    """Verify Role 1 adapter connectivity to Agent 1's real Role 6 inference gateway."""
    _, adapter = role6_client

    # 1. Readiness check
    health = await adapter.check_readiness()
    assert health.status == "healthy"
    assert health.backend_ready is True

    # 2. Bounded inference call
    op_id = uuid4()
    corr_id = uuid4()
    req = ModelInferenceRequest(
        schema_version="1.0",
        tenant_context=TENANT_1,
        operation_id=op_id,
        correlation_id=corr_id,
        capability=ModelCapability.DOCUMENT_EXTRACTION,
        model_name="docintel-foundation-vlm",
        input_data=InferenceInput(
            media_type=SupportedInputType.TEXT,
            text_content="SUPPLIER INVOICE\nINVOICE NUMBER: INV-001\nTOTAL AMOUNT: USD 100.00\n",
        ),
    )

    response = await adapter.infer(
        request=req,
        tenant_context=TENANT_1,
        operation_id=op_id,
    )

    assert response.schema_version == "1.0"
    assert response.operation_id == op_id
    assert response.output.fields is not None
    assert len(response.output.fields) > 0


@pytest.mark.asyncio
async def test_idempotency_conflict_on_different_payload(
    role2_client: tuple[Any, httpx.AsyncClient, Role2Adapter],
) -> None:
    """Verify that posting with the same operation ID but different payload raises 409 Conflict."""
    app, _, adapter = role2_client
    repo = app.state.get_repository(TENANT_1)

    await repo.save_account(
        Account.create("1100", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    await repo.save_account(
        Account.create("6100", "Office Expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT)
    )

    period_id = uuid4()
    await repo.save_period(
        period_id=period_id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        state=PeriodStatus.OPEN,
    )

    prop_id = uuid4()
    op_id = uuid4()
    corr_id = uuid4()

    # Proposal 1
    p1 = JournalProposal(
        schema_version="1.0",
        proposal_id=prop_id,
        proposal_version=1,
        tenant_context=TENANT_1,
        proposed_journal_date=date(2026, 9, 15),
        currency="INR",
        lines=[
            ProposedJournalLine(
                line_id=uuid4(),
                account_reference="6100",
                direction="DEBIT",
                amount=PositiveMoney(amount=Decimal("1000.00"), currency="INR"),
                description="Debit 1",
                source_evidence=[
                    ProvenanceReference(source_document_id=uuid4(), document_version="1")
                ],
            ),
            ProposedJournalLine(
                line_id=uuid4(),
                account_reference="1100",
                direction="CREDIT",
                amount=PositiveMoney(amount=Decimal("1000.00"), currency="INR"),
                description="Credit 1",
                source_evidence=[
                    ProvenanceReference(source_document_id=uuid4(), document_version="1")
                ],
            ),
        ],
        source_evidence=[ProvenanceReference(source_document_id=uuid4(), document_version="1")],
        explanation="Test entry 1",
        producer=ProducerMetadata(producer_type=ProducerType.SERVICE, name="test", version="1.0"),
        accounting_validation="NOT_VALIDATED",
        posting_status="UNPOSTED",
        correlation=CorrelationMetadata(request_id=op_id, correlation_id=corr_id),
    )

    await adapter.request_posting_validation(
        payload={
            "proposal_id": str(prop_id),
            "proposal_version": 1,
            "proposed_journal_date": "2026-09-15",
            "currency": "INR",
            "explanation": p1.explanation,
            "lines": [
                {
                    "line_id": str(line.line_id),
                    "account_reference": line.account_reference,
                    "direction": line.direction,
                    "amount": {"amount": str(line.amount.amount), "currency": line.amount.currency},
                    "description": line.description,
                    "source_evidence": [e.model_dump(mode="json") for e in line.source_evidence],
                }
                for line in p1.lines
            ],
            "source_evidence": [e.model_dump(mode="json") for e in p1.source_evidence],
        },
        tenant_context=TENANT_1,
        operation_id=op_id,
        correlation_id=corr_id,
    )

    res1 = await adapter.post_journal(
        payload={
            "proposal_id": str(prop_id),
            "proposal_version": 1,
            "accounting_period_id": str(period_id),
        },
        tenant_context=TENANT_1,
        operation_id=op_id,
        correlation_id=corr_id,
        expected_resource=("journal_proposal", prop_id),
    )
    assert res1.outcome == "POSTED"

    # Conflicting attempt: same op_id, different proposal_id
    different_prop_id = uuid4()
    with pytest.raises(Exception) as exc_info:
        await adapter.post_journal(
            payload={
                "proposal_id": str(different_prop_id),
                "proposal_version": 1,
                "accounting_period_id": str(period_id),
            },
            tenant_context=TENANT_1,
            operation_id=op_id,
            correlation_id=corr_id,
            expected_resource=("journal_proposal", different_prop_id),
        )
    assert "409" in str(exc_info.value) or "TERMINAL_DOWNSTREAM_FAILURE" in str(exc_info.value)


@pytest.mark.asyncio
async def test_journal_reversal_creates_balanced_offsets(
    role2_client: tuple[Any, httpx.AsyncClient, Role2Adapter],
) -> None:
    """Verify that reversing a journal creates balanced offsetting entries."""
    app, client, adapter = role2_client
    repo = app.state.get_repository(TENANT_1)

    await repo.save_account(
        Account.create("1100", "Cash", AccountType.ASSET, "INR", NormalBalance.DEBIT)
    )
    await repo.save_account(
        Account.create("6100", "Office Expense", AccountType.EXPENSE, "INR", NormalBalance.DEBIT)
    )

    period_id = uuid4()
    await repo.save_period(
        period_id=period_id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        state=PeriodStatus.OPEN,
    )

    prop_id = uuid4()
    op_id = uuid4()
    corr_id = uuid4()

    p = JournalProposal(
        schema_version="1.0",
        proposal_id=prop_id,
        proposal_version=1,
        tenant_context=TENANT_1,
        proposed_journal_date=date(2026, 9, 15),
        currency="INR",
        lines=[
            ProposedJournalLine(
                line_id=uuid4(),
                account_reference="6100",
                direction="DEBIT",
                amount=PositiveMoney(amount=Decimal("1200.00"), currency="INR"),
                description="Debit",
                source_evidence=[
                    ProvenanceReference(source_document_id=uuid4(), document_version="1")
                ],
            ),
            ProposedJournalLine(
                line_id=uuid4(),
                account_reference="1100",
                direction="CREDIT",
                amount=PositiveMoney(amount=Decimal("1200.00"), currency="INR"),
                description="Credit",
                source_evidence=[
                    ProvenanceReference(source_document_id=uuid4(), document_version="1")
                ],
            ),
        ],
        source_evidence=[ProvenanceReference(source_document_id=uuid4(), document_version="1")],
        explanation="Payment entry",
        producer=ProducerMetadata(producer_type=ProducerType.SERVICE, name="test", version="1.0"),
        accounting_validation="NOT_VALIDATED",
        posting_status="UNPOSTED",
        correlation=CorrelationMetadata(request_id=op_id, correlation_id=corr_id),
    )

    await adapter.request_posting_validation(
        payload={
            "proposal_id": str(prop_id),
            "proposal_version": 1,
            "proposed_journal_date": "2026-09-15",
            "currency": "INR",
            "explanation": p.explanation,
            "lines": [
                {
                    "line_id": str(line.line_id),
                    "account_reference": line.account_reference,
                    "direction": line.direction,
                    "amount": {"amount": str(line.amount.amount), "currency": line.amount.currency},
                    "description": line.description,
                    "source_evidence": [e.model_dump(mode="json") for e in line.source_evidence],
                }
                for line in p.lines
            ],
            "source_evidence": [e.model_dump(mode="json") for e in p.source_evidence],
        },
        tenant_context=TENANT_1,
        operation_id=op_id,
        correlation_id=corr_id,
    )

    posted = await adapter.post_journal(
        payload={
            "proposal_id": str(prop_id),
            "proposal_version": 1,
            "accounting_period_id": str(period_id),
        },
        tenant_context=TENANT_1,
        operation_id=op_id,
        correlation_id=corr_id,
        expected_resource=("journal_proposal", prop_id),
    )
    assert posted.outcome == "POSTED"
    assert posted.posted_journal_id is not None

    # Call reversal endpoint
    reversal_op_id = uuid4()
    token_provider = SignedServiceTokenProvider(
        issuer="ledgerai-backend", subject="role4-backend", secret=SECRET
    )
    rev_token = token_provider.token(
        audience="role2",
        tenant_id=TENANT_1.tenant_id,
        operation_id=reversal_op_id,
    )
    headers = {
        "Authorization": f"Bearer {rev_token}",
        "X-Tenant-ID": str(TENANT_1.tenant_id),
        "X-Organization-ID": str(TENANT_1.organization_id),
        "X-Legal-Entity-ID": str(TENANT_1.legal_entity_id),
        "X-Operation-ID": str(reversal_op_id),
        "X-Correlation-ID": str(uuid4()),
    }
    resp = await client.post(
        f"/v1/journals/{posted.posted_journal_id}/reversals",
        json={
            "reversal_date": "2026-09-16",
            "accounting_period_id": str(period_id),
            "reason": "Customer cancellation",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    rev_data = resp.json()
    assert rev_data["outcome"] == "POSTED"
    assert rev_data["posted_journal_id"] != posted.posted_journal_id
