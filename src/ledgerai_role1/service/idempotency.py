"""Thread-safe idempotency store for extraction operations."""

from __future__ import annotations

from threading import Lock
from uuid import UUID

from ledgerai_contracts.v1.documents import DocumentExtraction


class ExtractionIdempotencyStore:
    """Stores completed extraction results keyed by (tenant_id, operation_id)."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._store: dict[tuple[UUID, UUID], DocumentExtraction] = {}

    def get(self, tenant_id: UUID, operation_id: UUID) -> DocumentExtraction | None:
        with self._lock:
            return self._store.get((tenant_id, operation_id))

    def set(self, tenant_id: UUID, operation_id: UUID, result: DocumentExtraction) -> None:
        with self._lock:
            self._store[(tenant_id, operation_id)] = result

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
