"""Strict models and contracts for Role 6 Local Model Runtime."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    Field,
    StringConstraints,
    model_validator,
)

from ledgerai_contracts.v1.common import (
    Confidence,
    ContractModel,
    ProducerMetadata,
    SchemaVersion,
    UtcDateTime,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class ModelCapability(StrEnum):
    DOCUMENT_EXTRACTION = "DOCUMENT_EXTRACTION"
    DOCUMENT_CLASSIFICATION = "DOCUMENT_CLASSIFICATION"
    FIELD_EXTRACTION = "FIELD_EXTRACTION"
    EMBEDDING = "EMBEDDING"


class SupportedInputType(StrEnum):
    TEXT = "text/plain"
    PDF = "application/pdf"
    PNG = "image/png"
    JPEG = "image/jpeg"
    TIFF = "image/tiff"


class ModelBackendType(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    ONNX = "ONNX"
    PYTORCH = "PYTORCH"
    VLLM = "VLLM"
    LLAMACPP = "LLAMACPP"
    MOCK = "MOCK"


class DeviceType(StrEnum):
    CPU = "cpu"
    CUDA = "cuda"
    ROCM = "rocm"
    DIRECTML = "directml"


class ManifestResourceLimits(ContractModel):
    max_request_bytes: int = Field(default=10_485_760, ge=1_024, le=52_428_800)
    max_pages: int = Field(default=20, ge=1, le=100)
    max_image_pixels: int = Field(default=16_000_000, ge=10_000, le=100_000_000)
    max_input_tokens: int = Field(default=8_192, ge=16, le=131_072)
    max_output_tokens: int = Field(default=4_096, ge=16, le=32_768)
    wall_clock_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    max_concurrency: int = Field(default=10, ge=1, le=100)
    max_queue_depth: int = Field(default=50, ge=1, le=500)


class ModelManifest(ContractModel):
    schema_version: SchemaVersion
    model_id: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
    model_name: str = Field(min_length=1, max_length=128)
    backend_type: ModelBackendType
    immutable_revision: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    artifact_hashes: dict[str, str] = Field(
        min_length=1,
        description="Map of relative artifact filenames to SHA-256 hashes",
    )
    preprocessing_version: str = Field(pattern=r"^[a-zA-Z0-9._-]+$")
    supported_capabilities: list[ModelCapability] = Field(min_length=1)
    supported_input_types: list[SupportedInputType] = Field(min_length=1)
    limits: ManifestResourceLimits = Field(default_factory=ManifestResourceLimits)
    device_requirements: list[DeviceType] = Field(default_factory=lambda: [DeviceType.CPU])

    @model_validator(mode="after")
    def validate_hashes(self) -> ModelManifest:
        for fname, hsh in self.artifact_hashes.items():
            if not hsh or len(hsh) != 64 or not all(c in "0123456789abcdefABCDEF" for c in hsh):
                raise ValueError(f"artifact hash for {fname} must be a valid 64-character SHA-256")
        return self


SafeReferenceString = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9/_.-]+$",
    ),
]


class InferenceInput(ContractModel):
    media_type: SupportedInputType
    text_content: str | None = Field(default=None, max_length=1_000_000)
    storage_reference: SafeReferenceString | None = None
    page_count: int | None = Field(default=None, ge=1, le=100)
    pixel_count: int | None = Field(default=None, ge=1, le=100_000_000)

    @model_validator(mode="after")
    def require_at_least_one_source(self) -> InferenceInput:
        if self.text_content is None and self.storage_reference is None:
            raise ValueError("InferenceInput requires either text_content or storage_reference")
        return self


class ModelInferenceRequest(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    operation_id: UUID
    correlation_id: UUID
    causation_id: UUID | None = None
    capability: ModelCapability
    model_name: str = Field(min_length=1, max_length=128)
    model_version: str | None = Field(default=None, max_length=128)
    preprocessing_version: str | None = Field(default=None, max_length=64)
    input_data: InferenceInput
    temperature: Decimal = Field(default=Decimal("0.0"), ge=Decimal("0.0"), le=Decimal("2.0"))
    max_tokens: int | None = Field(default=None, ge=1, le=32_768)


class ProvenanceEntry(ContractModel):
    source_field: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    evidence_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    confidence: Confidence | None = None


class ExtractedFieldPrediction(ContractModel):
    field_name: str = Field(min_length=1, max_length=128)
    value: str | None = None
    confidence: Confidence
    provenance: list[ProvenanceEntry] = Field(default_factory=list)


class ClassificationPrediction(ContractModel):
    category: str = Field(min_length=1, max_length=128)
    confidence: Confidence
    provenance: list[ProvenanceEntry] = Field(default_factory=list)


class InferenceOutput(ContractModel):
    raw_completion: str | None = None
    fields: list[ExtractedFieldPrediction] = Field(default_factory=list)
    classification: ClassificationPrediction | None = None
    embedding: list[float] | None = Field(default=None, max_length=4096)


class RuntimeExecutionMetadata(ContractModel):
    backend_type: ModelBackendType
    backend_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    preprocessing_revision: str = Field(min_length=1)
    device: str = Field(min_length=1)
    warmup: bool = False
    queue_duration_ms: float = Field(ge=0)
    inference_duration_ms: float = Field(ge=0)
    tokens_prompt: int | None = Field(default=None, ge=0)
    tokens_completion: int | None = Field(default=None, ge=0)


class ModelInferenceResponse(ContractModel):
    schema_version: SchemaVersion
    tenant_context: EntityTenantContext
    operation_id: UUID
    correlation_id: UUID
    output: InferenceOutput
    execution_metadata: RuntimeExecutionMetadata
    producer: ProducerMetadata
    created_at: UtcDateTime


class RuntimeHealthStatus(ContractModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    backend_ready: bool
    manifest_valid: bool
    active_backend: ModelBackendType
    configured_model: str
    loaded_revision: str
    device: str
    active_concurrency: int = Field(ge=0)
    queue_depth: int = Field(ge=0)
    details: str | None = None
