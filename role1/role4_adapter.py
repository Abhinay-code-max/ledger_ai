"""Thin Role 4-to-Role 1 adapter with contract-specific mapping injected.

Role 4 owns its request/event wire contracts. The approved request decoder is
provided by the integration and maps its message to Role 1's normalized
``ProcessingRequest``; this module deliberately contains no wire-field names.
"""
from __future__ import annotations

from typing import Any, Protocol

from .async_service import AsyncRole1Service, ProcessingRequest


class ApprovedRequestMapper(Protocol):
    """Adapter implemented against Role 4's approved request contract."""

    def to_role1_request(self, message: Any) -> ProcessingRequest: ...


class Role4RequestAdapter:
    """Map an approved Role 4 request and submit it through Role 1 service."""

    def __init__(self, *, mapper: ApprovedRequestMapper, service: AsyncRole1Service):
        self._mapper, self._service = mapper, service

    async def handle(self, message: Any) -> dict[str, Any]:
        request = self._mapper.to_role1_request(message)
        if not isinstance(request, ProcessingRequest):
            raise TypeError("request mapper must return ProcessingRequest")
        return await self._service.submit(request)
