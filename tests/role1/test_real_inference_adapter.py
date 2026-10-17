"""Tests for RealDocumentUnderstandingBackend and inference adapter behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from ledgerai_contracts.v1.model_runtime import (
    InferenceInput,
    ModelBackendType,
    ModelCapability,
    ModelInferenceRequest,
    SupportedInputType,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role6.backend import (
    BackendError,
    ModelUnavailableError,
    RealDocumentUnderstandingBackend,
)
from ledgerai_role6.manifest import load_and_verify_manifest

MANIFEST_PATH = Path("models/manifests/ledgerai_docintel_v1.manifest.json")
TENANT_ID = uuid4()
ORG_ID = uuid4()
LEGAL_ENTITY_ID = uuid4()


@pytest.fixture
def tenant_context() -> EntityTenantContext:
    return EntityTenantContext(
        tenant_id=TENANT_ID,
        organization_id=ORG_ID,
        legal_entity_id=LEGAL_ENTITY_ID,
    )


def test_real_backend_rejects_when_weights_missing_and_fallback_disabled() -> None:
    manifest = load_and_verify_manifest(MANIFEST_PATH)
    backend = RealDocumentUnderstandingBackend(
        configured_model=manifest.model_name,
        model_weights_path=Path("non_existent_weights.safetensors"),
        allow_deterministic_fallback=False,
    )

    with pytest.raises(ModelUnavailableError, match="fallback is disabled"):
        asyncio.run(backend.initialize(manifest))


def test_real_backend_labels_fallback_transparently(tenant_context: EntityTenantContext) -> None:
    manifest = load_and_verify_manifest(MANIFEST_PATH)
    backend = RealDocumentUnderstandingBackend(
        configured_model=manifest.model_name,
        model_weights_path=Path("non_existent_weights.safetensors"),
        allow_deterministic_fallback=True,
    )

    async def run() -> None:
        await backend.initialize(manifest)
        assert not backend.is_neural_weights_loaded()
        assert backend.get_device() == "cpu-deterministic-fallback"

        req = ModelInferenceRequest(
            schema_version="1.0",
            tenant_context=tenant_context,
            operation_id=uuid4(),
            correlation_id=uuid4(),
            capability=ModelCapability.DOCUMENT_EXTRACTION,
            model_name=manifest.model_name,
            input_data=InferenceInput(
                media_type=SupportedInputType.TEXT,
                text_content=(
                    "SUPPLIER INVOICE\n"
                    "SUPPLIER: Acme Corp\n"
                    "INVOICE NUMBER: INV-100\n"
                    "TOTAL AMOUNT: USD 500.00\n"
                ),
            ),
        )

        output, metadata = await backend.infer(req, manifest)

        # Transparent fallback metadata
        assert metadata.backend_type == ModelBackendType.DETERMINISTIC
        assert metadata.device == "cpu-deterministic-fallback"
        assert "[FALLBACK_DETERMINISTIC]" in (output.raw_completion or "")

        # Verify correct extraction
        field_map = {f.field_name: f.value for f in output.fields}
        assert field_map.get("supplier_name") == "Acme Corp"
        assert field_map.get("invoice_number") == "INV-100"
        assert field_map.get("total_amount") == "500.00"

    asyncio.run(run())


def test_missing_fields_preserved_without_hallucination(
    tenant_context: EntityTenantContext,
) -> None:
    manifest = load_and_verify_manifest(MANIFEST_PATH)
    backend = RealDocumentUnderstandingBackend(
        configured_model=manifest.model_name,
        allow_deterministic_fallback=True,
    )

    async def run() -> None:
        await backend.initialize(manifest)

        # Document with NO customer name, NO due date, NO bank account
        req = ModelInferenceRequest(
            schema_version="1.0",
            tenant_context=tenant_context,
            operation_id=uuid4(),
            correlation_id=uuid4(),
            capability=ModelCapability.DOCUMENT_EXTRACTION,
            model_name=manifest.model_name,
            input_data=InferenceInput(
                media_type=SupportedInputType.TEXT,
                text_content="RECEIPT\nMERCHANT: Coffee Shop\nDATE: 2026-03-01\nTOTAL: USD 4.50\n",
            ),
        )

        output, _ = await backend.infer(req, manifest)
        field_names = {f.field_name for f in output.fields}

        # Preserved fields
        assert "supplier_name" in field_names
        assert "total_amount" in field_names
        assert "issue_date" in field_names

        # Missing fields MUST NOT be hallucinated
        assert "customer_name" not in field_names
        assert "due_date" not in field_names
        assert "bank_account_reference" not in field_names
        assert "document_number" not in field_names

    asyncio.run(run())


def test_arithmetic_mismatch_detected(tenant_context: EntityTenantContext) -> None:
    manifest = load_and_verify_manifest(MANIFEST_PATH)
    backend = RealDocumentUnderstandingBackend(
        configured_model=manifest.model_name,
        allow_deterministic_fallback=True,
    )

    async def run() -> None:
        await backend.initialize(manifest)

        req = ModelInferenceRequest(
            schema_version="1.0",
            tenant_context=tenant_context,
            operation_id=uuid4(),
            correlation_id=uuid4(),
            capability=ModelCapability.DOCUMENT_EXTRACTION,
            model_name=manifest.model_name,
            input_data=InferenceInput(
                media_type=SupportedInputType.TEXT,
                text_content=(
                    "SUPPLIER INVOICE\n"
                    "SUPPLIER: Faulty Math Corp\n"
                    "INVOICE NUMBER: INV-881\n"
                    "SUBTOTAL: USD 100.00\n"
                    "TAX: USD 10.00\n"
                    "TOTAL AMOUNT: USD 999.00\n"
                ),
            ),
        )

        output, _ = await backend.infer(req, manifest)
        field_map = {f.field_name: f.value for f in output.fields}

        assert "validation_issues" in field_map
        import json

        issues = json.loads(str(field_map["validation_issues"]))
        assert any(i["code"] == "ARITHMETIC_TOTAL_MISMATCH" for i in issues)

    asyncio.run(run())


def test_oversized_payload_rejected(tenant_context: EntityTenantContext) -> None:
    manifest = load_and_verify_manifest(MANIFEST_PATH)
    # Temporarily set lower limit to test backend enforcement
    manifest_limited = manifest.model_copy(
        update={"limits": manifest.limits.model_copy(update={"max_request_bytes": 1024})}
    )
    backend = RealDocumentUnderstandingBackend(
        configured_model=manifest.model_name,
        allow_deterministic_fallback=True,
    )

    async def run() -> None:
        await backend.initialize(manifest_limited)
        oversized_text = "A" * 2000

        req = ModelInferenceRequest(
            schema_version="1.0",
            tenant_context=tenant_context,
            operation_id=uuid4(),
            correlation_id=uuid4(),
            capability=ModelCapability.DOCUMENT_EXTRACTION,
            model_name=manifest_limited.model_name,
            input_data=InferenceInput(
                media_type=SupportedInputType.TEXT,
                text_content=oversized_text,
            ),
        )

        with pytest.raises(BackendError, match="exceeds limit"):
            await backend.infer(req, manifest_limited)

    asyncio.run(run())
