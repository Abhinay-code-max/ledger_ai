"""Legal job transitions, transactional outbox dispatch, and inbox deduplication."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import ColumnElement, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ledgerai_backend.core.observability import (
    dead_letters,
    inbox_duplicates,
    job_duration,
    job_transitions,
    outbox_pending_age,
    outbox_publications,
    publish_retries,
)
from ledgerai_backend.database.rls import set_tenant_context
from ledgerai_backend.ingestion.models import (
    ConsumerInbox,
    DeliveryStatus,
    JobStatus,
    OutboxEvent,
    ProcessingJob,
)
from ledgerai_backend.ports import EventPublisherPort

LEGAL_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.PROCESSING, JobStatus.FAILED}),
    JobStatus.PROCESSING: frozenset(
        {
            JobStatus.COMPLETED,
            JobStatus.REVIEW_REQUIRED,
            JobStatus.RETRY_SCHEDULED,
            JobStatus.FAILED,
            JobStatus.DEAD_LETTERED,
        }
    ),
    JobStatus.RETRY_SCHEDULED: frozenset({JobStatus.QUEUED, JobStatus.DEAD_LETTERED}),
    JobStatus.REVIEW_REQUIRED: frozenset({JobStatus.COMPLETED, JobStatus.FAILED}),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.FAILED: frozenset({JobStatus.QUEUED}),
    JobStatus.DEAD_LETTERED: frozenset(),
}


def transition_job(job: ProcessingJob, target: JobStatus, *, expected_version: int) -> None:
    if job.version != expected_version:
        raise ValueError("stale job version")
    if target not in LEGAL_TRANSITIONS[job.status]:
        raise ValueError("illegal job state transition")
    if target == JobStatus.PROCESSING and job.attempt_number >= job.maximum_attempts:
        raise ValueError("job attempt limit reached")
    if target == JobStatus.QUEUED and (
        job.retryable is not True or job.attempt_number >= job.maximum_attempts
    ):
        raise ValueError("job is not retryable")
    now = datetime.now(UTC)
    if target == JobStatus.PROCESSING:
        job.attempt_number += 1
        job.started_at = now
    elif target == JobStatus.COMPLETED:
        job.completed_at = now
        if job.started_at:
            job_duration.record(
                max(0.0, (now - job.started_at).total_seconds()), {"outcome": "completed"}
            )
    elif target in {JobStatus.FAILED, JobStatus.DEAD_LETTERED}:
        job.failed_at = now
        if job.started_at:
            job_duration.record(
                max(0.0, (now - job.started_at).total_seconds()),
                {"outcome": target.value.lower()},
            )
        if target == JobStatus.DEAD_LETTERED:
            dead_letters.add(1, {"source": "job"})
    job.status = target
    job.version += 1
    job_transitions.add(1, {"state": target.value})


async def dispatch_pending_outbox(
    session_factory: async_sessionmaker[AsyncSession],
    publisher: EventPublisherPort,
    *,
    tenant_id: UUID,
    event_id: UUID | None = None,
    batch_size: int = 50,
    maximum_attempts: int = 8,
) -> int:
    """Publish due outbox rows, optionally replaying one tenant-scoped event.

    ``event_id`` is deliberately an additional predicate, rather than a
    post-claim filter.  Operational recovery can therefore target one known
    event without a busy tenant queue consuming a bounded relay batch first.
    The row remains protected by the same tenant RLS context and row lock as
    normal relay operation.
    """
    published = 0
    async with session_factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        due: list[ColumnElement[bool]] = [
            OutboxEvent.status.in_([DeliveryStatus.PENDING, DeliveryStatus.FAILED]),
            (OutboxEvent.next_attempt_at.is_(None))
            | (OutboxEvent.next_attempt_at <= datetime.now(UTC)),
        ]
        if event_id is not None:
            due.append(OutboxEvent.event_id == event_id)
        rows = list(
            await session.scalars(
                select(OutboxEvent)
                .where(*due)
                .order_by(OutboxEvent.created_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            outbox_pending_age.record(
                max(0.0, (datetime.now(UTC) - row.created_at).total_seconds())
            )
            try:
                await asyncio.to_thread(
                    publisher.publish,
                    event_id=row.event_id,
                    event_type=row.event_type,
                    payload=row.payload_reference,
                )
            except Exception:
                row.attempt_count += 1
                row.last_error_code = "PUBLISH_FAILED"
                row.status = (
                    DeliveryStatus.DEAD_LETTERED
                    if row.attempt_count >= maximum_attempts
                    else DeliveryStatus.FAILED
                )
                if row.status == DeliveryStatus.FAILED:
                    base_delay = min(300.0, float(2 ** min(row.attempt_count, 8)))
                    jitter = (row.event_id.int % 1000) / 1000 * min(5.0, base_delay / 4)
                    delay = base_delay + jitter
                    row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
                    publish_retries.add(1)
                else:
                    dead_letters.add(1, {"source": "outbox"})
                outbox_publications.add(1, {"outcome": row.status.value.lower()})
            else:
                row.status = DeliveryStatus.COMPLETED
                row.published_at = datetime.now(UTC)
                row.last_error_code = None
                published += 1
                outbox_publications.add(1, {"outcome": "completed"})
    return published


async def claim_inbox_event(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    organization_id: UUID,
    legal_entity_id: UUID,
    consumer_name: str,
    consumer_version: str,
    event_id: UUID,
    event_type: str,
    schema_version: str,
) -> bool:
    statement = (
        insert(ConsumerInbox)
        .values(
            tenant_id=tenant_id,
            organization_id=organization_id,
            legal_entity_id=legal_entity_id,
            consumer_name=consumer_name,
            consumer_version=consumer_version,
            event_id=event_id,
            event_type=event_type,
            schema_version=schema_version,
            status=DeliveryStatus.PROCESSING,
        )
        .on_conflict_do_nothing(index_elements=["consumer_name", "event_id"])
        .returning(ConsumerInbox.id)
    )
    if await session.scalar(statement) is not None:
        return True
    existing = await session.scalar(
        select(ConsumerInbox)
        .where(
            ConsumerInbox.consumer_name == consumer_name,
            ConsumerInbox.event_id == event_id,
        )
        .with_for_update()
    )
    if existing is not None and existing.status == DeliveryStatus.FAILED:
        existing.status = DeliveryStatus.PROCESSING
        existing.consumer_version = consumer_version
        return True
    inbox_duplicates.add(1)
    return False


def finish_inbox_event(
    row: ConsumerInbox,
    *,
    succeeded: bool,
    retryable: bool = False,
    error_code: str | None = None,
    maximum_attempts: int = 5,
) -> None:
    if row.status != DeliveryStatus.PROCESSING:
        raise ValueError("inbox event is not processing")
    row.attempt_count += 1
    row.version += 1
    if succeeded:
        row.status = DeliveryStatus.COMPLETED
        row.processed_at = datetime.now(UTC)
        row.error_code = None
        return
    row.error_code = error_code or "CONSUMER_FAILED"
    if retryable and row.attempt_count < maximum_attempts:
        row.status = DeliveryStatus.FAILED
        return
    row.status = DeliveryStatus.DEAD_LETTERED
    dead_letters.add(1, {"source": "inbox"})
