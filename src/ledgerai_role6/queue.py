"""Concurrency limiter and FIFO request queue with tenant fairness."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import HTTPException, status


class ConcurrencyQueueError(RuntimeError):
    """Queue or concurrency failure."""


class RuntimeQueueManager:
    """Bounded active concurrency and waiting queue depth manager."""

    def __init__(
        self,
        *,
        max_concurrency: int = 10,
        max_queue_depth: int = 50,
        per_tenant_max_concurrency: int = 4,
    ) -> None:
        self.max_concurrency = max_concurrency
        self.max_queue_depth = max_queue_depth
        self.per_tenant_max_concurrency = per_tenant_max_concurrency

        self._active_count = 0
        self._queue_depth = 0
        self._tenant_active: dict[UUID, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._shutting_down = False

    def shutdown(self) -> None:
        self._shutting_down = True

    @property
    def active_concurrency(self) -> int:
        return self._active_count

    @property
    def queue_depth(self) -> int:
        return self._queue_depth

    @asynccontextmanager
    async def acquire(self, tenant_id: UUID) -> AsyncIterator[None]:
        if self._shutting_down:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Server is shutting down",
            )

        async with self._lock:
            # Check per-tenant concurrency
            if self._tenant_active[tenant_id] >= self.per_tenant_max_concurrency:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Per-tenant concurrency limit exceeded",
                )

            # Check queue depth saturation
            if self._queue_depth >= self.max_queue_depth:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Inference queue depth saturated",
                )

            self._queue_depth += 1

        acquired = False
        try:
            # Await semaphore for global active concurrency
            await self._semaphore.acquire()
            acquired = True
            async with self._lock:
                self._queue_depth -= 1
                self._active_count += 1
                self._tenant_active[tenant_id] += 1
            yield
        finally:
            if acquired:
                async with self._lock:
                    self._active_count = max(0, self._active_count - 1)
                    self._tenant_active[tenant_id] = max(0, self._tenant_active[tenant_id] - 1)
                self._semaphore.release()
            else:
                async with self._lock:
                    self._queue_depth = max(0, self._queue_depth - 1)
