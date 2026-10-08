from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID, uuid4

import pytest
from phase1_postgres_support import ACME_TENANT
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ledgerai_backend.database.rls import set_tenant_context
from ledgerai_backend.database.seed import stable_id
from ledgerai_backend.ingestion.models import (
    ConsumerInbox,
    DeliveryStatus,
    OutboxEvent,
)
from ledgerai_backend.workflow.reliability import (
    claim_inbox_event,
    dispatch_pending_outbox,
    finish_inbox_event,
)

pytestmark = pytest.mark.postgres


class RecordingPublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[UUID] = []

    def publish(self, *, event_id: UUID, event_type: str, payload: Mapping[str, object]) -> None:
        if self.fail:
            raise ConnectionError("synthetic broker outage")
        assert event_type in {
            "document.uploaded.v1",
            "transactions.imported.v1",
            "workflow.failed.v1",
        }
        assert "resource_id" in payload
        self.events.append(event_id)


@pytest.mark.asyncio
async def test_outbox_survives_publish_failure_and_recovers(runtime_engine) -> None:  # type: ignore[no-untyped-def]
    tenant_id = stable_id("nova:tenant")
    organization_id = stable_id("nova:organization")
    legal_entity_id = stable_id("nova:legal-entity")
    event_id = uuid4()
    factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        session.add(
            OutboxEvent(
                tenant_id=tenant_id,
                organization_id=organization_id,
                legal_entity_id=legal_entity_id,
                event_id=event_id,
                event_type="workflow.failed.v1",
                schema_version="1.0",
                producer="integration-test",
                payload_reference={"resource_type": "job", "resource_id": str(uuid4())},
                correlation_id=uuid4(),
                status=DeliveryStatus.PENDING,
            )
        )

    failed = RecordingPublisher(fail=True)
    assert (
        await dispatch_pending_outbox(
            factory, failed, tenant_id=tenant_id, event_id=event_id, batch_size=50
        )
        == 0
    )
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        row = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        assert row is not None
        assert row.status == DeliveryStatus.FAILED
        assert row.attempt_count == 1
        assert row.last_error_code == "PUBLISH_FAILED"
        assert row.next_attempt_at is not None
        row.next_attempt_at = None

    recovered = RecordingPublisher()
    assert (
        await dispatch_pending_outbox(
            factory, recovered, tenant_id=tenant_id, event_id=event_id, batch_size=50
        )
        >= 1
    )
    assert event_id in recovered.events
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        row = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        assert row is not None
        assert row.status == DeliveryStatus.COMPLETED
        assert row.published_at is not None


@pytest.mark.asyncio
async def test_targeted_outbox_replay_cannot_claim_a_foreign_tenant_event(runtime_engine) -> None:  # type: ignore[no-untyped-def]
    tenant_id = stable_id("nova:tenant")
    organization_id = stable_id("nova:organization")
    legal_entity_id = stable_id("nova:legal-entity")
    event_id = uuid4()
    factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        session.add(
            OutboxEvent(
                tenant_id=tenant_id,
                organization_id=organization_id,
                legal_entity_id=legal_entity_id,
                event_id=event_id,
                event_type="workflow.failed.v1",
                schema_version="1.0",
                producer="integration-test",
                payload_reference={"resource_type": "job", "resource_id": str(uuid4())},
                correlation_id=uuid4(),
                status=DeliveryStatus.PENDING,
            )
        )

    publisher = RecordingPublisher()
    assert (
        await dispatch_pending_outbox(
            factory, publisher, tenant_id=ACME_TENANT, event_id=event_id, batch_size=1
        )
        == 0
    )
    assert publisher.events == []


@pytest.mark.asyncio
async def test_inbox_claim_is_atomic_and_duplicate_safe(runtime_engine) -> None:  # type: ignore[no-untyped-def]
    tenant_id = stable_id("nova:tenant")
    organization_id = stable_id("nova:organization")
    legal_entity_id = stable_id("nova:legal-entity")
    event_id = uuid4()
    factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        first = await claim_inbox_event(
            session,
            tenant_id=tenant_id,
            organization_id=organization_id,
            legal_entity_id=legal_entity_id,
            consumer_name="role1-document-intelligence",
            consumer_version="stub-1",
            event_id=event_id,
            event_type="document.uploaded.v1",
            schema_version="1.0",
        )
        duplicate = await claim_inbox_event(
            session,
            tenant_id=tenant_id,
            organization_id=organization_id,
            legal_entity_id=legal_entity_id,
            consumer_name="role1-document-intelligence",
            consumer_version="stub-1",
            event_id=event_id,
            event_type="document.uploaded.v1",
            schema_version="1.0",
        )
        assert first is True
        assert duplicate is False
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        row = await session.scalar(select(ConsumerInbox).where(ConsumerInbox.event_id == event_id))
        assert row is not None
        finish_inbox_event(row, succeeded=False, retryable=True, error_code="TRANSIENT")

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        assert await claim_inbox_event(
            session,
            tenant_id=tenant_id,
            organization_id=organization_id,
            legal_entity_id=legal_entity_id,
            consumer_name="role1-document-intelligence",
            consumer_version="stub-2",
            event_id=event_id,
            event_type="document.uploaded.v1",
            schema_version="1.0",
        )
        row = await session.scalar(select(ConsumerInbox).where(ConsumerInbox.event_id == event_id))
        assert row is not None
        finish_inbox_event(row, succeeded=True)

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        assert not await claim_inbox_event(
            session,
            tenant_id=tenant_id,
            organization_id=organization_id,
            legal_entity_id=legal_entity_id,
            consumer_name="role1-document-intelligence",
            consumer_version="stub-2",
            event_id=event_id,
            event_type="document.uploaded.v1",
            schema_version="1.0",
        )
        rows = list(
            await session.scalars(select(ConsumerInbox).where(ConsumerInbox.event_id == event_id))
        )
        assert len(rows) == 1
        assert rows[0].status == DeliveryStatus.COMPLETED
        assert rows[0].attempt_count == 2
