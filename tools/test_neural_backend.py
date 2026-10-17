"""Standalone test script for RealDocumentUnderstandingBackend neural execution."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from ledgerai_contracts.v1.model_runtime import (
    InferenceInput,
    ModelCapability,
    ModelInferenceRequest,
    SupportedInputType,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role6.backend import RealDocumentUnderstandingBackend
from ledgerai_role6.manifest import load_and_verify_manifest

MANIFEST_PATH = Path("models/manifests/ledgerai_docintel_v1.manifest.json")


async def main() -> None:
    manifest = load_and_verify_manifest(MANIFEST_PATH)
    weights_dir = Path("models/artifacts/qwen2-vl-2b-instruct")

    backend = RealDocumentUnderstandingBackend(
        configured_model=manifest.model_name,
        model_weights_path=weights_dir,
        allow_deterministic_fallback=True,
    )
    await backend.initialize(manifest)
    print("Backend initialized.")
    print("Neural weights loaded:", backend.is_neural_weights_loaded())
    print("Device:", backend.get_device())

    tenant_ctx = EntityTenantContext(
        tenant_id=uuid4(),
        organization_id=uuid4(),
        legal_entity_id=uuid4(),
    )

    req = ModelInferenceRequest(
        schema_version="1.0",
        tenant_context=tenant_ctx,
        operation_id=uuid4(),
        correlation_id=uuid4(),
        capability=ModelCapability.DOCUMENT_EXTRACTION,
        model_name=manifest.model_name,
        input_data=InferenceInput(
            media_type=SupportedInputType.TEXT,
            text_content=(
                "SUPPLIER INVOICE\n"
                "SUPPLIER: Vertex Systems AG\n"
                "CUSTOMER: Nova Technologies Corp\n"
                "INVOICE NUMBER: VTX-2026-991\n"
                "ISSUE DATE: 2026-03-01\n"
                "DUE DATE: 2026-03-31\n"
                "CURRENCY: USD\n"
                "SUBTOTAL: USD 1000.00\n"
                "TAX: USD 100.00\n"
                "TOTAL AMOUNT: USD 1100.00\n"
            ),
        ),
    )

    output, metadata = await backend.infer(req, manifest)
    print("\nInference Output:")
    print("Backend type:", metadata.backend_type)
    print("Device:", metadata.device)
    print("Inference duration:", metadata.inference_duration_ms, "ms")
    print("Classification:", output.classification.category if output.classification else None)
    print("Extracted fields count:", len(output.fields))
    for f in output.fields[:6]:
        print(f"  - {f.field_name}: {f.value}")


if __name__ == "__main__":
    asyncio.run(main())
