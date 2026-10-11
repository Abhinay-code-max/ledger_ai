"""Direct compatibility test between Role 4's Role1Adapter and the Role 1 service."""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest

from ledgerai_backend.integration.adapters import (
    AdapterSecurity,
    Role1Adapter,
    SignedServiceTokenProvider,
)
from ledgerai_contracts.v1.documents import DocumentExtraction, FieldState
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role1.service.app import create_app
from ledgerai_role1.service.config import Role1Settings

SECRET = "x" * 32
TENANT_CONTEXT = EntityTenantContext(
    tenant_id=UUID("20000000-0000-0000-0000-000000000001"),
    organization_id=UUID("20000000-0000-0000-0000-000000000002"),
    legal_entity_id=UUID("20000000-0000-0000-0000-000000000003"),
)


@pytest.fixture
def role1_adapter() -> Role1Adapter:
    settings = Role1Settings(
        service_token_secret=SECRET,  # type: ignore[arg-type]
        audience="role1",
        environment="test",
    )
    app = create_app(settings)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://role1.test",
    )
    token_provider = SignedServiceTokenProvider(
        issuer="role4-orchestrator",
        subject="role4-backend",
        secret=SECRET,
    )
    return Role1Adapter(
        AdapterSecurity(
            base_url="http://role1.test",
            audience="role1",
            environment="test",
            maximum_attempts=1,
        ),
        token_provider,
        client=client,
    )


@pytest.mark.asyncio
async def test_role4_adapter_end_to_end_extraction(role1_adapter: Role1Adapter) -> None:
    operation_id = uuid4()
    document_id = uuid4()
    correlation_id = uuid4()

    doc_text = """SUPPLIER INVOICE
SUPPLIER: Nova Partners Ltd
INVOICE NUMBER: INV-2026-001
ISSUE DATE: 2026-01-15
SUBTOTAL: USD 1000.00
TAX: USD 80.00
TOTAL AMOUNT: USD 1080.00
1. Cloud Compute Cluster | Qty: 1 | Price: USD 1000.00 | Amount: USD 1000.00
"""

    extraction: DocumentExtraction = await role1_adapter.request_extraction(
        payload={
            "document_id": str(document_id),
            "document_version": "v1",
            "document_text": doc_text,
            "media_type": "text/plain",
        },
        tenant_context=TENANT_CONTEXT,
        operation_id=operation_id,
        correlation_id=correlation_id,
        expected_resource=("document", document_id),
    )

    # Assert contract model validity
    assert isinstance(extraction, DocumentExtraction)
    assert extraction.schema_version == "1.0"
    assert extraction.document_id == document_id
    assert extraction.tenant_context == TENANT_CONTEXT
    assert extraction.classification == "INVOICE"
    assert extraction.status == "COMPLETED"
    assert extraction.review_disposition == "NOT_REQUIRED"

    # Verify extracted fields
    total_field = next(f for f in extraction.fields if f.field_name == "total")
    assert total_field.state == FieldState.EXTRACTED
    assert total_field.value.amount == 1080.00 or str(total_field.value.amount) == "1080.00"  # type: ignore[union-attr]

    # Verify line items
    assert len(extraction.line_items) == 1
    assert extraction.line_items[0].description.value == "Cloud Compute Cluster"

    # Verify producer metadata includes model and template version
    assert extraction.producer.model_name == "docintel-foundation-vlm"
    assert extraction.producer.prompt_template_version == "nova-v1"
    assert extraction.producer.version == "1.0.0"

    await role1_adapter.aclose()
