"""Streaming-oriented, bounded normalization for hostile bank CSV input."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Literal, cast
from uuid import UUID, uuid5

from ledgerai_backend.ingestion.schemas import CsvColumnMapping, CsvRowError, ParsedTransaction
from ledgerai_contracts.v1.common import CorrelationMetadata, PositiveMoney, ProvenanceReference
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_contracts.v1.transactions import BankTransaction as ContractBankTransaction

DECIMAL_PATTERN = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")
FORMULA_PREFIXES = ("=", "+", "-", "@")
TRANSACTION_NAMESPACE = UUID("e520bcf8-c547-420c-92cc-7d2143ec952a")


class CsvStructureError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True, slots=True)
class CsvParseResult:
    rows: list[ParsedTransaction]
    errors: list[CsvRowError]


def _text(value: str | None, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError("required value is missing")
        return None
    cleaned = value.strip()
    if required and not cleaned:
        raise ValueError("required value is empty")
    if cleaned.startswith(FORMULA_PREFIXES):
        raise ValueError("formula-prefixed values are not accepted")
    return cleaned or None


def _date(value: str | None, *, required: bool = False) -> date | None:
    cleaned = _text(value, required=required)
    if cleaned is None:
        return None
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue
    raise ValueError("date is not in an accepted format")


def parse_bank_csv(
    content: bytes,
    *,
    mapping: CsvColumnMapping,
    maximum_rows: int,
    maximum_columns: int,
    maximum_cell_chars: int,
    tenant_context: EntityTenantContext,
    bank_account_id: UUID,
    import_id: UUID,
    request_id: UUID,
    correlation_id: UUID,
) -> CsvParseResult:
    if not content:
        raise CsvStructureError("EMPTY_FILE", "The CSV file is empty.")
    if b"\x00" in content:
        raise CsvStructureError("NUL_BYTE", "The CSV file contains a forbidden NUL byte.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvStructureError("INVALID_ENCODING", "The CSV file must be UTF-8.") from exc

    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames
        if not headers:
            raise CsvStructureError("MISSING_HEADERS", "The CSV file has no header row.")
        normalized_headers = [header.strip() for header in headers]
        if any(not header for header in normalized_headers):
            raise CsvStructureError("EMPTY_HEADER", "CSV headers cannot be empty.")
        if len(normalized_headers) != len(set(normalized_headers)):
            raise CsvStructureError("DUPLICATE_HEADER", "CSV headers must be unique.")
        if len(normalized_headers) > maximum_columns:
            raise CsvStructureError("TOO_MANY_COLUMNS", "The CSV has too many columns.")
        required = {mapping.booking_date, mapping.amount, mapping.currency, mapping.direction}
        if not required.issubset(normalized_headers):
            raise CsvStructureError("MISSING_REQUIRED_HEADER", "A required CSV header is missing.")
        parsed: list[ParsedTransaction] = []
        errors: list[CsvRowError] = []
        for source_row, row in enumerate(reader, start=2):
            if source_row - 1 > maximum_rows:
                raise CsvStructureError("TOO_MANY_ROWS", "The CSV has too many rows.")
            if None in row:
                raise CsvStructureError("MALFORMED_CSV", "A CSV row has excess columns.")
            if any(len(value or "") > maximum_cell_chars for value in row.values()):
                errors.append(
                    CsvRowError(
                        source_row_number=source_row,
                        error_code="CELL_TOO_LARGE",
                        safe_message="A cell exceeds the allowed length.",
                    )
                )
                continue
            try:
                direction = _text(row.get(mapping.direction), required=True)
                if direction is None or direction.upper() not in {"DEBIT", "CREDIT"}:
                    raise ValueError("direction must be DEBIT or CREDIT")
                amount_text = _text(row.get(mapping.amount), required=True)
                if amount_text is None or not DECIMAL_PATTERN.fullmatch(amount_text):
                    raise ValueError("amount must be an unsigned canonical decimal string")
                try:
                    amount = Decimal(amount_text)
                except InvalidOperation as exc:
                    raise ValueError("amount is invalid") from exc
                currency = _text(row.get(mapping.currency), required=True)
                if currency is None or not re.fullmatch(r"[A-Za-z]{3}", currency):
                    raise ValueError("currency must be a three-letter ISO code")
                currency = currency.upper()
                booking_date = _date(row.get(mapping.booking_date), required=True)
                assert booking_date is not None
                value_date = _date(row.get(mapping.value_date)) if mapping.value_date else None
                narration = _text(row.get(mapping.narration)) if mapping.narration else None
                reference = _text(row.get(mapping.reference)) if mapping.reference else None
                counterparty_name = (
                    _text(row.get(mapping.counterparty_name)) if mapping.counterparty_name else None
                )
                counterparty_account = (
                    _text(row.get(mapping.counterparty_account))
                    if mapping.counterparty_account
                    else None
                )
                external_source_id = (
                    _text(row.get(mapping.external_source_id))
                    if mapping.external_source_id
                    else None
                )
                canonical = "|".join(
                    (
                        str(bank_account_id),
                        booking_date.isoformat(),
                        value_date.isoformat() if value_date else "",
                        format(amount, "f"),
                        currency,
                        direction.upper(),
                        narration or "",
                        reference or "",
                        external_source_id or "",
                    )
                )
                fingerprint = sha256(canonical.encode()).hexdigest()
                transaction_id = uuid5(
                    TRANSACTION_NAMESPACE, f"{tenant_context.tenant_id}:{fingerprint}"
                )
                typed_direction = cast(Literal["DEBIT", "CREDIT"], direction.upper())
                ContractBankTransaction(
                    schema_version="1.0",
                    transaction_id=transaction_id,
                    tenant_context=tenant_context,
                    bank_account_id=bank_account_id,
                    import_batch_id=import_id,
                    source_row_number=source_row,
                    booking_date=booking_date,
                    value_date=value_date,
                    money=PositiveMoney(amount=amount, currency=currency),
                    direction=typed_direction,
                    narration=narration or "",
                    reference=reference,
                    counterparty=None,
                    external_source_id=external_source_id,
                    normalization_status="NORMALIZED",
                    provenance=[
                        ProvenanceReference(source_row=source_row, evidence_hash=fingerprint)
                    ],
                    content_fingerprint=fingerprint,
                    correlation=CorrelationMetadata(
                        request_id=request_id, correlation_id=correlation_id
                    ),
                )
                parsed.append(
                    ParsedTransaction(
                        source_row_number=source_row,
                        booking_date=booking_date,
                        value_date=value_date,
                        amount=amount,
                        currency=currency,
                        direction=typed_direction,
                        narration=narration or "",
                        reference=reference,
                        counterparty_name=counterparty_name,
                        counterparty_account=counterparty_account,
                        external_source_id=external_source_id,
                        source_fingerprint=fingerprint,
                    )
                )
            except ValueError:
                errors.append(
                    CsvRowError(
                        source_row_number=source_row,
                        error_code="INVALID_ROW",
                        safe_message="The row contains invalid transaction data.",
                    )
                )
    except csv.Error as exc:
        raise CsvStructureError("MALFORMED_CSV", "The CSV structure is malformed.") from exc
    return CsvParseResult(parsed, errors)
