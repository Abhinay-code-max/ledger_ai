"""Stable safe error envelope for frontend and cross-service consumers."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from ledgerai_contracts.v1.common import ContractModel, SafeMessage, SchemaVersion

ErrorCategory = Literal[
    "INPUT_VALIDATION",
    "AUTHENTICATION",
    "AUTHORIZATION",
    "CONFLICT",
    "STATE_TRANSITION",
    "RATE_LIMIT",
    "DOWNSTREAM",
    "INTERNAL",
]


class FieldError(ContractModel):
    field: str
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    message: SafeMessage


class ErrorEnvelope(ContractModel):
    """External error data. Messages must be sanitized before this model is constructed."""

    schema_version: SchemaVersion
    category: ErrorCategory
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    message: SafeMessage
    internal_error_id: UUID | None = None
    request_id: UUID
    correlation_id: UUID | None = None
    field_errors: list[FieldError] = Field(default_factory=list)
    retryable: bool | None = None
    help_reference: str | None = None
