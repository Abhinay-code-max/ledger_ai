"""Canonical ontology schema and contract conversion."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ledgerai_contracts.v1.common import (
    CorrelationMetadata,
    Money,
    ProducerMetadata,
    ProducerType,
    ProvenanceReference,
    ValidationIssue,
)
from ledgerai_contracts.v1.documents import (
    DocumentExtraction,
    ExtractedField,
    ExtractedLineItem,
    ExtractionProcessingStatus,
    FieldState,
    ReviewDisposition,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role1.ontology.fields import (
    CRITICAL_FIELDS_BY_DOC_TYPE,
    ONTOLOGY_VERSION,
    DocumentType,
)


class AnnotatedProvenance(BaseModel):
    """Normalized provenance for an extracted token or field value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_number: int = Field(ge=1)
    x: Decimal = Field(ge=Decimal("0"))
    y: Decimal = Field(ge=Decimal("0"))
    width: Decimal = Field(gt=Decimal("0"))
    height: Decimal = Field(gt=Decimal("0"))
    text_snippet: str | None = Field(default=None, max_length=500)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    evidence_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class AnnotatedLineItem(BaseModel):
    """Line item with strict Decimal arithmetic."""

    model_config = ConfigDict(extra="forbid")

    line_number: int = Field(ge=1)
    description: str = Field(min_length=1)
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    line_amount: Decimal
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"), default=Decimal("1.0"))
    provenance: list[AnnotatedProvenance] = Field(default_factory=list)

    @field_validator("quantity", "unit_price", "line_amount", mode="before")
    @classmethod
    def reject_float_money(cls, v: object) -> object:
        if isinstance(v, float):
            raise ValueError("Floating point is forbidden for financial amounts")
        if isinstance(v, (int, str)):
            return Decimal(str(v))
        return v


class CanonicalDocumentData(BaseModel):
    """Canonical ontology representation of a document's extracted fields."""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    document_number: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    supplier_name: str | None = None
    customer_name: str | None = None
    supplier_tax_id: str | None = None
    customer_tax_id: str | None = None
    purchase_order_reference: str | None = None
    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None
    currency: str = Field(pattern=r"^[A-Z]{3}$", default="USD")
    bank_account_reference: str | None = None
    line_items: list[AnnotatedLineItem] = Field(default_factory=list)
    confidences: dict[str, Decimal] = Field(default_factory=dict)
    provenances: dict[str, list[AnnotatedProvenance]] = Field(default_factory=dict)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)

    @field_validator("subtotal", "tax_amount", "total_amount", mode="before")
    @classmethod
    def reject_floats(cls, v: object) -> object:
        if isinstance(v, float):
            raise ValueError("Floating point is forbidden for financial amounts")
        if isinstance(v, (int, str)) and v is not None:
            return Decimal(str(v))
        return v

    @field_validator("bank_account_reference")
    @classmethod
    def mask_bank_account(cls, v: str | None) -> str | None:
        if v is None:
            return None
        # Enforce masking: never allow raw plain account numbers
        cleaned = re.sub(r"[\s-]", "", v)
        if len(cleaned) > 4 and cleaned.isalnum() and not cleaned.startswith("*"):
            return f"****{cleaned[-4:]}"
        return v

    @model_validator(mode="after")
    def validate_arithmetic_consistency(self) -> CanonicalDocumentData:
        if (
            self.subtotal is not None
            and self.tax_amount is not None
            and self.total_amount is not None
        ):
            expected_total = self.subtotal + self.tax_amount
            if self.total_amount != expected_total:
                self.validation_issues.append(
                    ValidationIssue(
                        code="ARITHMETIC_TOTAL_MISMATCH",
                        message=(
                            f"Subtotal {self.subtotal} + tax {self.tax_amount} "
                            f"does not match total {self.total_amount}"
                        ),
                        field="total",
                        severity="ERROR",
                    )
                )
        if self.line_items and self.total_amount is not None:
            line_sum = sum(item.line_amount for item in self.line_items)
            # If line sum does not match subtotal or total
            reference_target = self.subtotal if self.subtotal is not None else self.total_amount
            if line_sum != reference_target:
                self.validation_issues.append(
                    ValidationIssue(
                        code="LINE_ITEM_TOTAL_MISMATCH",
                        message=(
                            f"Line items sum {line_sum} differs from "
                            f"reference amount {reference_target}"
                        ),
                        field="line_items",
                        severity="WARNING",
                    )
                )
        return self


def to_contract_extraction(
    data: CanonicalDocumentData,
    *,
    extraction_id: UUID,
    document_id: UUID,
    document_version: str,
    tenant_context: EntityTenantContext,
    correlation: CorrelationMetadata,
    producer: ProducerMetadata | None = None,
    created_at_iso: str | None = None,
) -> DocumentExtraction:
    """Convert CanonicalDocumentData into the strict DocumentExtraction contract."""
    from datetime import UTC, datetime

    from ledgerai_contracts.v1.common import BoundingBox

    now = datetime.now(UTC) if created_at_iso is None else datetime.fromisoformat(created_at_iso)

    prod = producer or ProducerMetadata(
        producer_type=ProducerType.MODEL,
        name="ledgerai-docintel-baseline",
        version="1.0.0",
        model_name="docintel-hybrid-v1",
        model_version="1.0.0",
        prompt_template_version="nova-v1",
        algorithm_version=ONTOLOGY_VERSION,
    )

    critical_fields = CRITICAL_FIELDS_BY_DOC_TYPE.get(data.document_type, frozenset())
    extracted_fields: list[ExtractedField] = []

    def make_provenance_refs(provs: list[AnnotatedProvenance]) -> list[ProvenanceReference]:
        refs: list[ProvenanceReference] = []
        for p in provs:
            refs.append(
                ProvenanceReference(
                    source_document_id=document_id,
                    document_version=document_version,
                    page_number=p.page_number,
                    bounding_box=BoundingBox(
                        page=p.page_number,
                        x=p.x,
                        y=p.y,
                        width=p.width,
                        height=p.height,
                    ),
                    confidence=p.confidence,
                    evidence_hash=p.evidence_hash or "a" * 64,
                )
            )
        return refs

    # Field mapping
    field_entries = [
        ("supplier_name", data.supplier_name, False),
        ("customer_name", data.customer_name, False),
        ("invoice_number", data.document_number, False),
        ("invoice_date", str(data.issue_date) if data.issue_date else None, False),
        ("due_date", str(data.due_date) if data.due_date else None, False),
        ("supplier_tax_id", data.supplier_tax_id, False),
        ("customer_tax_id", data.customer_tax_id, False),
        ("purchase_order", data.purchase_order_reference, False),
        ("bank_account_reference", data.bank_account_reference, False),
        (
            "subtotal",
            Money(amount=data.subtotal, currency=data.currency)
            if data.subtotal is not None
            else None,
            True,
        ),
        (
            "tax",
            Money(amount=data.tax_amount, currency=data.currency)
            if data.tax_amount is not None
            else None,
            True,
        ),
        (
            "total",
            Money(amount=data.total_amount, currency=data.currency)
            if data.total_amount is not None
            else None,
            True,
        ),
    ]

    for fname, fval, _is_money in field_entries:
        is_crit = fname in critical_fields
        conf = data.confidences.get(fname, Decimal("0.95") if fval is not None else Decimal("0"))
        provs = data.provenances.get(fname, [])
        prov_refs = make_provenance_refs(provs)

        if fval is None:
            extracted_fields.append(
                ExtractedField(
                    field_name=fname,
                    is_critical=is_crit,
                    state=FieldState.MISSING,
                    value=None,
                    confidence=None,
                    provenance=[],
                )
            )
        else:
            state = FieldState.EXTRACTED if conf >= Decimal("0.70") else FieldState.LOW_CONFIDENCE
            if not prov_refs:
                # Default document-level fallback provenance if not populated
                prov_refs = [
                    ProvenanceReference(
                        source_document_id=document_id,
                        document_version=document_version,
                        page_number=1,
                        confidence=conf,
                        evidence_hash="a" * 64,
                    )
                ]
            extracted_fields.append(
                ExtractedField(
                    field_name=fname,
                    is_critical=is_crit,
                    state=state,
                    value=fval,
                    confidence=conf,
                    provenance=prov_refs,
                )
            )

    # Line items
    contract_lines: list[ExtractedLineItem] = []
    for item in data.line_items:
        item_prov = make_provenance_refs(item.provenance)
        if not item_prov:
            item_prov = [
                ProvenanceReference(
                    source_document_id=document_id,
                    document_version=document_version,
                    page_number=1,
                    confidence=item.confidence,
                    evidence_hash="a" * 64,
                )
            ]
        desc_field = ExtractedField(
            field_name="description",
            is_critical=False,
            state=FieldState.EXTRACTED,
            value=item.description,
            confidence=item.confidence,
            provenance=item_prov,
        )
        amt_field = ExtractedField(
            field_name="line_amount",
            is_critical=False,
            state=FieldState.EXTRACTED,
            value=Money(amount=item.line_amount, currency=item.currency),
            confidence=item.confidence,
            provenance=item_prov,
        )
        qty_field = None
        if item.quantity is not None:
            qty_field = ExtractedField(
                field_name="quantity",
                is_critical=False,
                state=FieldState.EXTRACTED,
                value=str(item.quantity),
                confidence=item.confidence,
                provenance=item_prov,
            )
        price_field = None
        if item.unit_price is not None:
            price_field = ExtractedField(
                field_name="unit_price",
                is_critical=False,
                state=FieldState.EXTRACTED,
                value=Money(amount=item.unit_price, currency=item.currency),
                confidence=item.confidence,
                provenance=item_prov,
            )

        contract_lines.append(
            ExtractedLineItem(
                line_number=item.line_number,
                description=desc_field,
                quantity=qty_field,
                unit_price=price_field,
                line_amount=amt_field,
            )
        )

    # Review disposition check
    reasons: list[str] = []
    has_crit_issues = any(
        f.is_critical and f.state in {FieldState.MISSING, FieldState.LOW_CONFIDENCE}
        for f in extracted_fields
    )
    if has_crit_issues:
        reasons.append("CRITICAL_FIELD_MISSING_OR_LOW_CONFIDENCE")
    has_error_issues = any(i.severity == "ERROR" for i in data.validation_issues)
    if has_error_issues:
        reasons.append("VALIDATION_ERROR_DETECTED")

    disposition = ReviewDisposition.REVIEW_REQUIRED if reasons else ReviewDisposition.NOT_REQUIRED

    classification: Literal["INVOICE", "RECEIPT", "BANK_STATEMENT", "UNKNOWN"]
    c_class = data.document_type.to_contract_classification()
    if c_class in {"INVOICE", "RECEIPT", "BANK_STATEMENT", "UNKNOWN"}:
        classification = c_class  # type: ignore[assignment]
    else:
        classification = "UNKNOWN"

    return DocumentExtraction(
        schema_version="1.0",
        extraction_id=extraction_id,
        document_id=document_id,
        document_version=document_version,
        tenant_context=tenant_context,
        classification=classification,
        fields=extracted_fields,
        line_items=contract_lines,
        validation_issues=data.validation_issues,
        status=ExtractionProcessingStatus.COMPLETED,
        review_disposition=disposition,
        review_reason_codes=reasons,
        producer=prod,
        created_at=now,
        updated_at=now,
        correlation=correlation,
    )
