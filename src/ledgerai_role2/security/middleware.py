"""Security middleware: size limits, concurrency controls, and diagnostic sanitization."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from typing import Any, cast

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_DANGEROUS_PATTERNS = re.compile(
    r"(?:select\b|insert\b|update\b|delete\b|drop\b|alter\b|table\b|"
    r"traceback|psycopg|sqlalchemy|postgres|password|secret|bearer)",
    re.IGNORECASE,
)


def sanitize_diagnostic_message(msg: str) -> str:
    """Ensure no SQL statements, tracebacks, or secrets leak into diagnostic messages."""
    if not msg:
        return "An internal service error occurred."
    if _DANGEROUS_PATTERNS.search(msg):
        return "An error occurred during accounting core processing."
    return msg[:500]


class Role2SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        *,
        max_request_bytes: int = 1_048_576,
        concurrency_limit: int = 100,
    ) -> None:
        super().__init__(app)
        self.max_request_bytes = max_request_bytes
        self.semaphore = asyncio.Semaphore(concurrency_limit)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_request_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "code": "REQUEST_TOO_LARGE",
                            "message": (
                                f"Request size exceeds limit of {self.max_request_bytes} bytes."
                            ),
                        },
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "code": "INVALID_CONTENT_LENGTH",
                        "message": "Invalid content length header.",
                    },
                )

        if self.semaphore.locked():
            return JSONResponse(
                status_code=503,
                content={
                    "code": "CONCURRENCY_LIMIT_EXCEEDED",
                    "message": "Service is busy; concurrency limit reached.",
                },
            )

        async with self.semaphore:
            try:
                response = await call_next(request)
                return cast(Response, response)
            except Exception as exc:  # noqa: BLE001
                safe_msg = sanitize_diagnostic_message(str(exc))
                return JSONResponse(
                    status_code=500,
                    content={"code": "INTERNAL_ERROR", "message": safe_msg},
                )
