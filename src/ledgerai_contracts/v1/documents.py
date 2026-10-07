"""Document intake and extraction evidence contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, GetJsonSchemaHandler, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from ledgerai_contracts.v1.common import (
    ActorReference,
    Confidence,
    ContractModel,
    CorrelationMetadata,
    Money,
    ProducerMetadata,
    ProvenanceReference,
    SchemaVersion,
    UtcDateTime,
    ValidationIssue,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class DocumentLifecycle(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"


class StorageReference(ContractModel):
    """Opaque immutable locator; never an OS path or credential-bearing URL."""

    object_key: str = Field(min_length=1)
    storage_version: str | None = None


class DocumentMetadata(ContractModel):
    schema_version: SchemaVersion
    document_id: UUID
    tenant_context: EntityTenantContext
    storage: StorageReference
    original_filename: str = Field(min_length=1, description="Untrusted display metadata")
    detected_media_type: str = Field(pattern=r"^[\w.+-]+/[\w.+-]+$")
    byte_size: int = Field(ge=0)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    hash_algorithm: Literal["SHA-256"] = "SHA-256"
    document_category: str | None = None
    upload_actor: ActorReference
    uploaded_at: UtcDateTime
    lifecycle_status: DocumentLifecycle
    correlation: CorrelationMetadata


class FieldState(StrEnum):
    EXTRACTED = "EXTRACTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MISSING = "MISSING"


class ExtractionProcessingStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReviewDisposition(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEWED = "REVIEWED"


FieldValue = str | Decimal | date | bool | Money


class ExtractedField(ContractModel):
    field_name: str = Field(min_length=1)
    is_critical: bool
    state: FieldState
    value: FieldValue | None = None
    confidence: Confidence | None = None
    provenance: list[ProvenanceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def preserve_missing_state(self) -> ExtractedField:
        if self.state == FieldState.MISSING and self.value is not None:
            raise ValueError("missing fields cannot contain a value")
        if self.state != FieldState.MISSING and self.value is None:
            raise ValueError("non-missing fields require a value")
        if self.state == FieldState.LOW_CONFIDENCE and self.confidence is None:
            raise ValueError("low-confidence fields require confidence evidence")
        return self


class ExtractedLineItem(ContractModel):
    line_number: int = Field(ge=1)
    description: ExtractedField
    quantity: ExtractedField | None = None
    unit_price: ExtractedField | None = None
    line_amount: ExtractedField


class DocumentExtraction(ContractModel):
    schema_version: SchemaVersion
    extraction_id: UUID
    document_id: UUID
    document_version: str = Field(min_length=1)
    tenant_context: EntityTenantContext
    classification: Literal["INVOICE", "RECEIPT", "BANK_STATEMENT", "UNKNOWN"]
    fields: list[ExtractedField]
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    status: ExtractionProcessingStatus
    review_disposition: ReviewDisposition
    review_reason_codes: list[str]
    producer: ProducerMetadata
    created_at: UtcDateTime
    updated_at: UtcDateTime
    correlation: CorrelationMetadata

    @model_validator(mode="after")
    def require_review_for_unresolved_critical_evidence(self) -> DocumentExtraction:
        fields = list(self.fields)
        for line in self.line_items:
            fields.extend(
                field
                for field in (line.description, line.quantity, line.unit_price, line.line_amount)
                if field is not None
            )
        unresolved_critical = any(
            field.is_critical and field.state in {FieldState.LOW_CONFIDENCE, FieldState.MISSING}
            for field in fields
        )
        invalid_or_conflicting = any(issue.severity == "ERROR" for issue in self.validation_issues)
        needs_review = unresolved_critical or invalid_or_conflicting
        if needs_review and self.review_disposition == ReviewDisposition.NOT_REQUIRED:
            raise ValueError("unresolved critical extraction evidence requires review")
        if (
            self.review_disposition == ReviewDisposition.REVIEW_REQUIRED
            and not self.review_reason_codes
        ):
            raise ValueError("REVIEW_REQUIRED requires at least one review reason code")
        if self.review_disposition == ReviewDisposition.NOT_REQUIRED and self.review_reason_codes:
            raise ValueError("NOT_REQUIRED cannot carry review reason codes")
        if self.review_disposition == ReviewDisposition.REVIEWED and self.status != "COMPLETED":
            raise ValueError("only completed extraction processing can be marked REVIEWED")
        return self

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        schema = handler(core_schema)
        review_signal = {
            "properties": {
                "review_disposition": {"enum": ["REVIEW_REQUIRED", "REVIEWED"]},
                "review_reason_codes": {"minItems": 1},
            },
            "required": ["review_disposition", "review_reason_codes"],
        }
        schema["allOf"] = [
            {
                "if": {
                    "properties": {
                        "fields": {
                            "contains": {
                                "properties": {
                                    "is_critical": {"const": True},
                                    "state": {"enum": ["LOW_CONFIDENCE", "MISSING"]},
                                },
                                "required": ["is_critical", "state"],
                            }
                        }
                    },
                    "required": ["fields"],
                },
                "then": review_signal,
            },
            {
                "if": {
                    "properties": {
                        "validation_issues": {
                            "contains": {
                                "properties": {"severity": {"const": "ERROR"}},
                                "required": ["severity"],
                            }
                        }
                    },
                    "required": ["validation_issues"],
                },
                "then": review_signal,
            },
            {
                "if": {
                    "properties": {"review_disposition": {"const": "REVIEW_REQUIRED"}},
                    "required": ["review_disposition"],
                },
                "then": {
                    "properties": {"review_reason_codes": {"minItems": 1}},
                    "required": ["review_reason_codes"],
                },
            },
            {
                "if": {
                    "properties": {"review_disposition": {"const": "NOT_REQUIRED"}},
                    "required": ["review_disposition"],
                },
                "then": {
                    "properties": {"review_reason_codes": {"maxItems": 0}},
                    "required": ["review_reason_codes"],
                },
            },
            {
                "if": {
                    "properties": {"review_disposition": {"const": "REVIEWED"}},
                    "required": ["review_disposition"],
                },
                "then": {
                    "properties": {"status": {"const": "COMPLETED"}},
                    "required": ["status"],
                },
            },
        ]
        schema["x-ledgerai-pydantic-invariants"] = [
            "Critical low-confidence or missing line-item fields also require review.",
            "All ERROR validation issues require review.",
        ]
        return schema
