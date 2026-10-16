"""Bounded, tenant-scoped invoice document vertical slice.

Document contents and model responses are untrusted data. This module never
executes, follows, or treats document text as instructions.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass
from typing import Any, BinaryIO, Protocol

from .validator import ContractError, validate_extraction

LOG = logging.getLogger(__name__)
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_PAGES = 20
MAX_PAGE_PIXELS = 20_000_000
MAX_TOTAL_PIXELS = 60_000_000
REVIEW_CONFIDENCE = 0.90
PIPELINE_VERSION = "role1-phase2"
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
DECIMAL_PATTERN = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")
SUPPORTED = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}
FIELD_NAMES = ("vendor_name", "gstin", "invoice_number", "invoice_date", "currency",
               "taxable_amount", "cgst", "sgst", "igst", "tax", "total",
               "purchase_order_reference")


@dataclass(frozen=True)
class DocumentReference:
    document_id: str
    tenant_id: str
    content_sha256: str
    media_type: str
    page_count: int


class DocumentStore(Protocol):
    def open_read(self, *, tenant_id: str, document_id: str) -> BinaryIO: ...


class InvoiceModel(Protocol):
    model_version: str

    def classify_and_extract(self, *, pages: tuple[bytes, ...], media_type: str,
                             correlation_id: str) -> dict[str, Any]: ...


class PipelineError(Exception):
    def __init__(self, code: str, message: str, *, retriable: bool = False):
        super().__init__(message)
        self.code, self.retriable = code, retriable


def _read_bounded(store: DocumentStore, ref: DocumentReference) -> bytes:
    try:
        with store.open_read(tenant_id=ref.tenant_id, document_id=ref.document_id) as stream:
            data = stream.read(MAX_DOCUMENT_BYTES + 1)
    except Exception as exc:
        # Do not include backend exception text: it may contain identifiers or secrets.
        raise PipelineError("DOCUMENT_RETRIEVAL_FAILED", "Document retrieval failed", retriable=True) from exc
    if not isinstance(data, bytes) or not data:
        raise PipelineError("DOCUMENT_EMPTY", "Document is empty or unreadable")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise PipelineError("DOCUMENT_TOO_LARGE", "Document exceeds the processing size limit")
    digest = hashlib.sha256(data).hexdigest()
    if digest != ref.content_sha256:
        raise PipelineError("DOCUMENT_HASH_MISMATCH", "Retrieved document does not match its immutable reference")
    return data


def _convert(data: bytes, media_type: str) -> tuple[bytes, ...]:
    if media_type not in SUPPORTED:
        raise PipelineError("UNSUPPORTED_MEDIA_TYPE", "Supported formats are PDF, PNG, JPEG, and TIFF")
    try:
        import fitz  # PyMuPDF
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise PipelineError("PROCESSOR_UNAVAILABLE", "Document conversion dependencies are unavailable", retriable=True) from exc
    try:
        pages: list[bytes] = []
        total_pixels = 0
        if media_type == "application/pdf":
            with fitz.open(stream=data, filetype="pdf") as pdf:
                if pdf.is_encrypted or pdf.page_count < 1 or pdf.page_count > MAX_PAGES:
                    raise PipelineError("PDF_PAGE_LIMIT", "PDF is encrypted, empty, or exceeds the page limit")
                for page in pdf:
                    rect = page.rect
                    if rect.width * rect.height > MAX_PAGE_PIXELS:
                        raise PipelineError("PAGE_TOO_LARGE", "PDF page exceeds the pixel limit")
                    total_pixels += int(rect.width * rect.height)
                    if total_pixels > MAX_TOTAL_PIXELS:
                        raise PipelineError("DOCUMENT_TOO_COMPLEX", "Document exceeds the total pixel limit")
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False)
                    if pix.width * pix.height > MAX_PAGE_PIXELS:
                        raise PipelineError("PAGE_TOO_LARGE", "Rendered page exceeds the pixel limit")
                    image = Image.open(io.BytesIO(pix.tobytes("png")))
                    image = ImageOps.exif_transpose(image).convert("RGB")
                    out = io.BytesIO(); image.save(out, format="JPEG", quality=90, optimize=True)
                    pages.append(out.getvalue())
        else:
            with Image.open(io.BytesIO(data)) as image:
                count = getattr(image, "n_frames", 1)
                if count < 1 or count > MAX_PAGES:
                    raise PipelineError("IMAGE_PAGE_LIMIT", "Image frame count exceeds the page limit")
                for frame in range(count):
                    image.seek(frame)
                    expected_format = {"image/png": "PNG", "image/jpeg": "JPEG", "image/tiff": "TIFF"}[media_type]
                    if image.format != expected_format:
                        raise PipelineError("MALFORMED_DOCUMENT", "Image bytes do not match the declared media type")
                    if image.width * image.height > MAX_PAGE_PIXELS:
                        raise PipelineError("PAGE_TOO_LARGE", "Image page exceeds the pixel limit")
                    total_pixels += image.width * image.height
                    if total_pixels > MAX_TOTAL_PIXELS:
                        raise PipelineError("DOCUMENT_TOO_COMPLEX", "Document exceeds the total pixel limit")
                    converted = ImageOps.exif_transpose(image.copy()).convert("RGB")
                    out = io.BytesIO(); converted.save(out, format="JPEG", quality=90, optimize=True)
                    pages.append(out.getvalue())
        if not pages:
            raise PipelineError("DOCUMENT_EMPTY", "Document contains no pages")
        return tuple(pages)
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError("MALFORMED_DOCUMENT", "Document could not be safely decoded") from exc


def _missing(note: str) -> dict[str, Any]:
    return {"state": "missing", "value": None, "confidence": None,
            "provenance": {"source": "none", "locators": [], "note": note}}


def _date_warning(value: str) -> str | None:
    """Accept only unambiguous calendar dates; retain the source string verbatim."""
    try:
        parsed = date.fromisoformat(value)
        return None if parsed.isoformat() == value else "Invoice date is not canonical ISO YYYY-MM-DD"
    except (TypeError, ValueError):
        return "Invoice date is invalid or ambiguous; human review required"


def _money_decimal(value: Any) -> Decimal | None:
    if not isinstance(value, dict) or not isinstance(value.get("amount"), str):
        return None
    try:
        return Decimal(value["amount"])
    except InvalidOperation:
        return None


def _valid_money(value: Any) -> bool:
    return (isinstance(value, dict) and set(value) == {"amount", "currency"}
            and isinstance(value["amount"], str) and len(value["amount"]) <= 100
            and DECIMAL_PATTERN.fullmatch(value["amount"]) is not None
            and isinstance(value["currency"], str)
            and re.fullmatch(r"[A-Z]{3}", value["currency"]) is not None)


def _total_warnings(fields: dict[str, Any]) -> list[str]:
    subtotal_name = "subtotal" if fields.get("subtotal", {}).get("value") is not None else "taxable_amount"
    subtotal = _money_decimal(fields.get(subtotal_name, {}).get("value"))
    tax = _money_decimal(fields.get("tax", {}).get("value"))
    total = _money_decimal(fields.get("total", {}).get("value"))
    warnings = []
    if subtotal is not None and tax is not None and total is not None:
        currencies = [fields.get(n, {}).get("value", {}).get("currency")
                      for n in (subtotal_name, "tax", "total")]
        if len(set(currencies)) > 1:
            warnings.append("Subtotal, tax, and total currencies differ")
        else:
            # Inputs are bounded to 100 characters; a wider context prevents
            # Decimal's default precision from rounding this validation check.
            with localcontext() as context:
                context.prec = 256
                if subtotal + tax != total:
                    warnings.append("Subtotal plus tax does not equal total")
    component_names = ("cgst", "sgst", "igst")
    components = [_money_decimal(fields.get(n, {}).get("value")) for n in component_names]
    if tax is not None and all(v is not None for v in components):
        component_currencies = [fields.get(n, {}).get("value", {}).get("currency") for n in component_names]
        tax_currency = fields.get("tax", {}).get("value", {}).get("currency")
        if len(set(component_currencies + [tax_currency])) > 1:
            warnings.append("Tax component currencies differ")
        else:
            with localcontext() as context:
                context.prec = 256
                if sum(components, Decimal(0)) != tax:
                    warnings.append("Tax components do not equal tax")
    return warnings


def _failure(ref: DocumentReference, correlation_id: str, code: str, message: str,
             retriable: bool, *, extraction_id: str, media_type: str | None = None) -> dict[str, Any]:
    # Page count is part of the immutable reference, including early failures.
    return {"contract_version": "role1.document-extraction.v1", "extraction_id": extraction_id,
            "document": {"document_id": ref.document_id, "tenant_id": ref.tenant_id,
                         "content_sha256": ref.content_sha256, "media_type": media_type or ref.media_type,
                         "page_count": ref.page_count}, "correlation_id": correlation_id, "status": "failure",
            "classification": {"class": "unknown", "confidence": None,
                               "provenance": {"source": "none", "locators": []}},
            "model_metadata": {"model_version": "unavailable", "pipeline_version": PIPELINE_VERSION},
            "fields": {}, "line_items": [],
            "failure": {"code": code, "message": message, "retriable": retriable}}


def process_invoice(*, reference: DocumentReference, store: DocumentStore,
                    model: InvoiceModel, correlation_id: str, extraction_id: str) -> dict[str, Any]:
    """Retrieve, convert, extract, and validate one immutable document version."""
    if (not isinstance(reference.document_id, str) or not reference.document_id.strip()
            or not isinstance(reference.tenant_id, str) or not reference.tenant_id.strip()
            or not isinstance(correlation_id, str) or not correlation_id.strip()
            or not isinstance(extraction_id, str) or not extraction_id.strip()
            or not isinstance(reference.media_type, str) or not reference.media_type.strip()
            or not isinstance(reference.content_sha256, str)
            or not re.fullmatch(r"[a-f0-9]{64}", reference.content_sha256)
            or type(reference.page_count) is not int or reference.page_count < 1):
        raise ValueError("Invalid immutable document reference or request metadata")
    data: bytes | None = None
    try:
        if reference.page_count > MAX_PAGES:
            raise PipelineError("DOCUMENT_PAGE_LIMIT", "Document exceeds the page limit")
        if reference.media_type not in SUPPORTED:
            raise PipelineError("UNSUPPORTED_MEDIA_TYPE", "Supported formats are PDF, PNG, JPEG, and TIFF")
        data = _read_bounded(store, reference)
        pages = _convert(data, reference.media_type)
        if len(pages) != reference.page_count:
            raise PipelineError("DOCUMENT_METADATA_MISMATCH", "Retrieved page count differs from the immutable reference")
        try:
            raw = model.classify_and_extract(pages=pages, media_type=reference.media_type,
                                             correlation_id=correlation_id)
        except Exception as exc:
            raise PipelineError("MODEL_UNAVAILABLE", "Invoice extraction service failed", retriable=True) from exc
        if not isinstance(raw, dict) or set(raw) != {"class", "confidence", "classification_locator", "fields"}:
            raise PipelineError("INVALID_MODEL_OUTPUT", "Model response did not match the expected extraction shape")
        doc_class = raw["class"]
        if doc_class not in {"invoice", "unknown"}:
            raise PipelineError("INVALID_MODEL_OUTPUT", "Model returned a classification outside this invoice slice")
        loc = raw["classification_locator"]
        if doc_class == "invoice" and (not isinstance(loc, dict) or type(loc.get("page")) is not int or not 1 <= loc["page"] <= len(pages)):
            raise PipelineError("INVALID_MODEL_OUTPUT", "Invoice classification lacks valid page provenance")
        fields_in = raw["fields"]
        if not isinstance(fields_in, dict) or fields_in.keys() - set(FIELD_NAMES):
            raise PipelineError("INVALID_MODEL_OUTPUT", "Model returned unknown or malformed fields")
        fields: dict[str, Any] = {}
        field_warnings: dict[str, list[str]] = {}
        needs_review = doc_class == "unknown"
        class_confidence = raw["confidence"]
        if type(class_confidence) not in (int, float) or not 0 <= class_confidence <= 1:
            raise PipelineError("INVALID_MODEL_OUTPUT", "Model returned invalid classification confidence")
        force_uncertain = doc_class == "unknown" or class_confidence < REVIEW_CONFIDENCE
        needs_review |= force_uncertain
        for name in FIELD_NAMES:
            value = fields_in.get(name)
            if value is None:
                fields[name] = _missing("No value was returned by extraction")
                needs_review = True
                continue
            if not isinstance(value, dict):
                raise PipelineError("INVALID_MODEL_OUTPUT", "A field response has an invalid shape")
            is_money = name in {"taxable_amount", "cgst", "sgst", "igst", "tax", "total"}
            if value.get("state") == "conflicting":
                if set(value) != {"state", "candidates"} or not isinstance(value["candidates"], list) or not 2 <= len(value["candidates"]) <= 10:
                    raise PipelineError("INVALID_MODEL_OUTPUT", "Conflicting fields require 2 to 10 candidates")
                candidates = []
                locators = []
                for candidate in value["candidates"]:
                    if not isinstance(candidate, dict) or set(candidate) != {"value", "confidence", "page", "region", "quote"}:
                        raise PipelineError("INVALID_MODEL_OUTPUT", "A conflict candidate has an invalid shape")
                    page, region, quote = candidate["page"], candidate["region"], candidate["quote"]
                    if type(page) is not int or not 1 <= page <= len(pages) or not isinstance(region, str) or not region.strip() or len(region) > 200 or not isinstance(quote, str) or len(quote) > 4000:
                        raise PipelineError("INVALID_MODEL_OUTPUT", "A conflict candidate lacks valid provenance")
                    confidence = candidate["confidence"]
                    if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
                        raise PipelineError("INVALID_MODEL_OUTPUT", "A conflict candidate has invalid confidence")
                    extracted = candidate["value"]
                    if is_money:
                        if not _valid_money(extracted):
                            raise PipelineError("INVALID_MODEL_OUTPUT", "A monetary candidate must use a decimal string and currency")
                    elif not isinstance(extracted, str) or not extracted.strip() or len(extracted) > 2000:
                        raise PipelineError("INVALID_MODEL_OUTPUT", "A text candidate must be a bounded non-empty string")
                    locator = {"page": page, "region": region, "quote": quote}
                    locators.append(locator)
                    candidates.append({"value": extracted, "provenance": {"source": "vlm", "locators": [locator]}})
                if len({json.dumps(candidate["value"], sort_keys=True) for candidate in candidates}) < 2:
                    raise PipelineError("INVALID_MODEL_OUTPUT", "Conflicting candidates must contain distinct values")
                fields[name] = {"state": "conflicting", "value": None, "confidence": None,
                                "provenance": {"source": "vlm", "locators": locators,
                                               "note": "Conflicting source values; no value selected"},
                                "candidates": candidates}
                needs_review = True
                continue
            if set(value) != {"value", "confidence", "page", "region", "quote"}:
                raise PipelineError("INVALID_MODEL_OUTPUT", "A field response has an invalid shape")
            page = value["page"]
            if type(page) is not int or not 1 <= page <= len(pages) or not isinstance(value["region"], str) or not value["region"].strip():
                raise PipelineError("INVALID_MODEL_OUTPUT", "A field response has invalid provenance")
            confidence = value["confidence"]
            if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
                raise PipelineError("INVALID_MODEL_OUTPUT", "A field response has invalid confidence")
            extracted = value["value"]
            if is_money:
                if not _valid_money(extracted):
                    raise PipelineError("INVALID_MODEL_OUTPUT", "A monetary field must use a decimal string and currency")
            elif not isinstance(extracted, str) or not extracted.strip():
                raise PipelineError("INVALID_MODEL_OUTPUT", "A text field must be a non-empty string")
            if isinstance(extracted, str) and len(extracted) > 2000:
                raise PipelineError("INVALID_MODEL_OUTPUT", "A text field exceeds the output limit")
            if len(value["region"]) > 200 or not isinstance(value["quote"], str) or len(value["quote"]) > 4000:
                raise PipelineError("INVALID_MODEL_OUTPUT", "Field provenance exceeds the output limit")
            state = "uncertain" if force_uncertain or confidence < REVIEW_CONFIDENCE else "observed"
            if name == "invoice_date":
                warning = _date_warning(extracted)
                if warning:
                    field_warnings.setdefault(name, []).append(warning)
            if name == "gstin" and not GSTIN_PATTERN.fullmatch(extracted):
                field_warnings.setdefault(name, []).append("GSTIN format is invalid; human review required")
            needs_review |= state == "uncertain"
            fields[name] = {"state": state, "value": extracted, "confidence": confidence,
                            "provenance": {"source": "vlm", "locators": [{"page": page,
                                           "region": value["region"], "quote": value["quote"]}]}}
        for name, messages in field_warnings.items():
            fields[name]["state"] = "uncertain"
            fields[name]["provenance"]["note"] = "; ".join(messages)
            needs_review = True
        for warning in _total_warnings(fields):
            # Keep model amounts untouched; mark a present value for review.
            target = next((fields.get(name) for name in ("total", "tax", "taxable_amount")
                           if fields.get(name, {}).get("value") is not None
                           and fields.get(name, {}).get("state") != "conflicting"), None)
            if target is not None:
                target["state"] = "uncertain"
                prior = target["provenance"].get("note")
                target["provenance"]["note"] = (prior + "; " if prior else "") + warning
                needs_review = True
        # A low-confidence or unknown class is never promoted to verified success.
        if doc_class == "unknown" or any(f["state"] == "missing" for f in fields.values()):
            needs_review = True
        result = {"contract_version": "role1.document-extraction.v1", "extraction_id": extraction_id,
                  "document": {"document_id": reference.document_id, "tenant_id": reference.tenant_id,
                              "content_sha256": reference.content_sha256, "media_type": reference.media_type,
                              "page_count": len(pages)}, "correlation_id": correlation_id,
                  "status": "review_required" if needs_review else "success",
                  "classification": {"class": doc_class, "confidence": class_confidence,
                                      "provenance": {"source": "vlm", "locators": [loc] if doc_class == "invoice" else []}},
                  "model_metadata": {"model_version": str(getattr(model, "model_version", "unknown")),
                                     "pipeline_version": PIPELINE_VERSION},
                  "fields": fields, "line_items": []}
        validate_extraction(result)
        _validate_schema(result)
        return result
    except PipelineError as exc:
        result = _failure(reference, correlation_id, exc.code, str(exc), exc.retriable,
                          extraction_id=extraction_id)
    except (ContractError, KeyError, TypeError, ValueError) as exc:
        result = _failure(reference, correlation_id, "INVALID_MODEL_OUTPUT", "Extraction output failed deterministic validation", False,
                          extraction_id=extraction_id)
    except Exception:
        result = _failure(reference, correlation_id, "INTERNAL_ERROR", "Document processing failed", False,
                          extraction_id=extraction_id)
    try:
        validate_extraction(result)
        _validate_schema(result)
    except ContractError:
        # Invalid reference metadata cannot be made contract-valid; avoid echoing it.
        LOG.error("Role 1 failed to construct a valid failure envelope")
        raise
    return result


def _validate_schema(result: dict[str, Any]) -> None:
    """Validate against the versioned schema as well as Python cross-field rules."""
    try:
        validator = _schema_validator()
    except ImportError as exc:
        raise ContractError("jsonschema dependency unavailable") from exc
    errors = list(validator.iter_errors(result))
    if errors:
        raise ContractError("JSON Schema validation failed: " + "; ".join(e.message for e in errors[:3]))


@lru_cache(maxsize=1)
def _schema_validator():
    """Load and check the immutable versioned schema once per process."""
    from jsonschema import Draft202012Validator
    schema_path = Path(__file__).parent / "contract" / "extraction-v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)
