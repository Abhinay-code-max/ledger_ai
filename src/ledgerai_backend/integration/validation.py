"""Deterministic validation for externally produced extraction evidence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ledgerai_backend.core.observability import extraction_validations
from ledgerai_contracts.v1.documents import DocumentExtraction, FieldState


@dataclass(frozen=True, slots=True)
class ExtractionValidation:
    outcome: str
    reason_codes: tuple[str, ...]


def _value(extraction: DocumentExtraction, name: str) -> object | None:
    matches = [
        field for field in extraction.fields if field.field_name == name and field.value is not None
    ]
    if len(matches) > 1 and len({str(field.value) for field in matches}) > 1:
        raise ValueError(f"conflicting duplicate field: {name}")
    return matches[0].value if matches else None


def validate_extraction(extraction: DocumentExtraction) -> ExtractionValidation:
    reasons: list[str] = []
    fields = list(extraction.fields)
    for line in extraction.line_items:
        fields.extend(
            filter(None, (line.description, line.quantity, line.unit_price, line.line_amount))
        )
    if any(field.state != FieldState.MISSING and not field.provenance for field in fields):
        reasons.append("MISSING_PROVENANCE")
    if any(
        field.is_critical and field.state in {FieldState.MISSING, FieldState.LOW_CONFIDENCE}
        for field in fields
    ):
        reasons.append("CRITICAL_EVIDENCE_REVIEW")
    if extraction.classification == "INVOICE":
        for required in ("invoice_number", "invoice_date", "total"):
            if _value(extraction, required) is None:
                reasons.append(f"MISSING_{required.upper()}")
    try:
        subtotal, tax, total = (_value(extraction, name) for name in ("subtotal", "tax", "total"))
        if all(value is not None for value in (subtotal, tax, total)):

            def amount(value: object) -> Decimal:
                inner = getattr(value, "amount", value)
                return Decimal(str(inner))

            if amount(subtotal) + amount(tax) != amount(total):
                reasons.append("TOTAL_ARITHMETIC_MISMATCH")
    except (InvalidOperation, ValueError):
        reasons.append("INVALID_DECIMAL")
    if any(issue.severity == "ERROR" for issue in extraction.validation_issues):
        reasons.append("EXTERNAL_VALIDATION_ERROR")
    blocking = {"INVALID_DECIMAL", "TOTAL_ARITHMETIC_MISMATCH", "EXTERNAL_VALIDATION_ERROR"}
    outcome = (
        "BLOCKED"
        if blocking.intersection(reasons)
        else "REVIEW_REQUIRED"
        if reasons
        else "VALIDATED"
    )
    extraction_validations.add(1, {"outcome": outcome})
    return ExtractionValidation(outcome, tuple(dict.fromkeys(reasons)))
