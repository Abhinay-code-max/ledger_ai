"""Safe API errors encoded with the Phase 0 contract."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ledgerai_contracts.v1.errors import ErrorEnvelope, FieldError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    category: str
    code: str
    message: str


def _ids(request: Request) -> tuple[UUID, UUID]:
    request_id = UUID(request.state.request_id)
    correlation_id = UUID(request.state.correlation_id)
    return request_id, correlation_id


def error_response(
    request: Request,
    *,
    status_code: int,
    category: str,
    code: str,
    message: str,
    field_errors: list[FieldError] | None = None,
    internal_error_id: UUID | None = None,
) -> JSONResponse:
    request_id, correlation_id = _ids(request)
    envelope = ErrorEnvelope(
        schema_version="1.0",
        category=category,  # type: ignore[arg-type]
        code=code,
        message=message,
        internal_error_id=internal_error_id,
        request_id=request_id,
        correlation_id=correlation_id,
        field_errors=field_errors or [],
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(
        request,
        status_code=exc.status_code,
        category=exc.category,
        code=exc.code,
        message=exc.message,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = []
    for error in exc.errors()[:25]:
        location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
        fields.append(
            FieldError(
                field=location or "request",
                code="INVALID_VALUE",
                message="The supplied value is invalid.",
            )
        )
    return error_response(
        request,
        status_code=422,
        category="INPUT_VALIDATION",
        code="REQUEST_VALIDATION_FAILED",
        message="The request could not be validated.",
        field_errors=fields,
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    internal_error_id = uuid4()
    logger.exception(
        "unhandled request failure",
        extra={"fields": {"internal_error_id": str(internal_error_id)}},
    )
    return error_response(
        request,
        status_code=500,
        category="INTERNAL",
        code="INTERNAL_ERROR",
        message="The request could not be completed.",
        internal_error_id=internal_error_id,
    )


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope, "description": "Authentication failed"},
    403: {"model": ErrorEnvelope, "description": "Permission denied"},
    404: {"model": ErrorEnvelope, "description": "Resource not found"},
    422: {"model": ErrorEnvelope, "description": "Request validation failed"},
}
