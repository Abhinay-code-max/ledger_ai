"""Bounded API schemas for secure ingestion and workflow resources."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class UploadInitiateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: UUID | None = None
    original_filename: str = Field(min_length=1, max_length=255)
    media_type: Literal["application/pdf", "image/jpeg", "image/png"]
    byte_size: int = Field(gt=0, le=52_428_800)
    sha256: Sha256


class UploadInitiateResponse(BaseModel):
    document_id: UUID
    upload_id: UUID
    upload_url: str
    expires_in_seconds: int
    status: str


class UploadCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha256: Sha256
    byte_size: int = Field(gt=0, le=52_428_800)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    legal_entity_id: UUID
    original_filename: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    version_number: int
    expected_media_type: str
    detected_media_type: str | None
    expected_byte_size: int
    actual_byte_size: int | None
    expected_sha256: str
    actual_sha256: str | None
    status: str
    failure_code: str | None
    created_at: datetime
    completed_at: datetime | None


class DocumentList(BaseModel):
    items: list[DocumentResponse]
    next_cursor: UUID | None


class CsvColumnMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_date: str = Field(default="booking_date", min_length=1, max_length=80)
    value_date: str | None = Field(default="value_date", max_length=80)
    amount: str = Field(default="amount", min_length=1, max_length=80)
    currency: str = Field(default="currency", min_length=1, max_length=80)
    direction: str = Field(default="direction", min_length=1, max_length=80)
    narration: str | None = Field(default="narration", max_length=80)
    reference: str | None = Field(default="reference", max_length=80)
    counterparty_name: str | None = Field(default="counterparty_name", max_length=80)
    counterparty_account: str | None = Field(default="counterparty_account", max_length=80)
    external_source_id: str | None = Field(default="external_source_id", max_length=80)


class ParsedTransaction(BaseModel):
    source_row_number: int
    booking_date: date
    value_date: date | None
    amount: Decimal
    currency: str
    direction: Literal["DEBIT", "CREDIT"]
    narration: str
    reference: str | None
    counterparty_name: str | None
    counterparty_account: str | None
    external_source_id: str | None
    source_fingerprint: Sha256


class CsvRowError(BaseModel):
    source_row_number: int
    error_code: str
    safe_message: str


class TransactionImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    legal_entity_id: UUID
    bank_account_id: UUID
    status: str
    accepted_count: int
    rejected_count: int
    created_at: datetime
    updated_at: datetime


class ImportErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source_row_number: int
    error_code: str
    safe_message: str


class BankTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    import_id: UUID
    bank_account_id: UUID
    source_row_number: int
    booking_date: date
    value_date: date | None
    amount: Decimal
    currency: str
    direction: str
    narration: str
    reference: str | None
    source_fingerprint: str


class BankTransactionList(BaseModel):
    items: list[BankTransactionResponse]
    next_cursor: UUID | None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_type: str
    handler_version: str
    status: str
    attempt_number: int
    maximum_attempts: int
    input_reference: str
    output_reference: str | None
    retryable: bool | None
    error_code: str | None
    safe_error_message: str | None
    correlation_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime
