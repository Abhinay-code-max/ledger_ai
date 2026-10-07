"""Celery/Redis dispatch adapter hidden behind JobQueuePort."""

from __future__ import annotations

from uuid import UUID

from celery import Celery  # type: ignore[import-untyped]

from ledgerai_backend.core.config import Settings
from ledgerai_backend.core.observability import dependency_failures, queue_dispatches


class CeleryJobQueue:
    def __init__(self, settings: Settings) -> None:
        if not settings.redis_url:
            raise ValueError("redis_url is required")
        redis_url = settings.redis_url.get_secret_value()
        self._app = Celery("ledgerai", broker=redis_url, backend=redis_url)
        self._app.conf.update(
            task_acks_late=True,
            task_acks_on_failure_or_timeout=False,
            worker_prefetch_multiplier=1,
            task_soft_time_limit=270,
            task_time_limit=300,
            task_routes={"ledgerai.process_job": {"queue": settings.queue_default}},
            task_publish_retry=True,
            task_publish_retry_policy={
                "max_retries": settings.queue_max_attempts,
                "interval_start": 0,
                "interval_step": 1,
                "interval_max": 5,
            },
            broker_connection_retry_on_startup=True,
            broker_transport_options={"visibility_timeout": 360},
            worker_cancel_long_running_tasks_on_connection_loss=True,
        )

    def enqueue(
        self,
        *,
        job_id: UUID,
        queue_name: str,
        correlation_id: UUID,
        event_id: UUID | None = None,
    ) -> str:
        try:
            task = self._app.send_task(
                "ledgerai.process_job",
                kwargs={
                    "job_id": str(job_id),
                    "correlation_id": str(correlation_id),
                    "event_id": str(event_id) if event_id else None,
                },
                queue=queue_name,
                task_id=str(job_id),
            )
        except Exception:
            dependency_failures.add(1, {"dependency": "redis", "operation": "enqueue"})
            raise
        queue_dispatches.add(1, {"workload": "job", "outcome": "accepted"})
        return str(task.id)


class CeleryEventPublisher:
    def __init__(self, settings: Settings) -> None:
        if not settings.redis_url:
            raise ValueError("redis_url is required")
        redis_url = settings.redis_url.get_secret_value()
        self._app = Celery("ledgerai-events", broker=redis_url, backend=redis_url)
        self._queue = settings.queue_default
        self._app.conf.update(
            task_acks_late=True,
            task_acks_on_failure_or_timeout=False,
            worker_prefetch_multiplier=1,
            task_soft_time_limit=270,
            task_time_limit=300,
            task_routes={"ledgerai.consume_event": {"queue": settings.queue_default}},
            task_publish_retry=True,
            task_publish_retry_policy={
                "max_retries": settings.queue_max_attempts,
                "interval_start": 0,
                "interval_step": 1,
                "interval_max": 5,
            },
            broker_connection_retry_on_startup=True,
            broker_transport_options={"visibility_timeout": 360},
            worker_cancel_long_running_tasks_on_connection_loss=True,
        )

    def publish(self, *, event_id: UUID, event_type: str, payload: dict[str, object]) -> None:
        try:
            self._app.send_task(
                "ledgerai.consume_event",
                kwargs={"event_id": str(event_id), "event_type": event_type, "payload": payload},
                queue=self._queue,
                task_id=str(event_id),
            )
        except Exception:
            dependency_failures.add(1, {"dependency": "redis", "operation": "publish"})
            raise
        queue_dispatches.add(1, {"workload": "event", "outcome": "accepted"})
