"""Strictly scoped reset for the synthetic NOVA demonstration tenant."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import boto3  # type: ignore[import-untyped]
import psycopg
import redis

from ledgerai_backend.core.config import Settings
from ledgerai_backend.database.seed import seed, stable_id

NOVA_TENANT_ID = stable_id("nova:tenant")
NOVA_ORGANIZATION_ID = stable_id("nova:organization")
NOVA_ENTITY_ID = stable_id("nova:legal-entity")

# Children precede parents. Identity and authorization rows are intentionally absent.
TENANT_TABLES = (
    "role2_statement_lines",
    "role2_statement_snapshots",
    "role2_journal_lines",
    "role2_posted_journals",
    "role2_period_close_operations",
    "role2_posting_operations",
    "role2_proposal_registry",
    "role2_accounts",
    "role2_accounting_periods",
    "financial_statement_lines",
    "financial_statement_snapshots",
    "posting_confirmations",
    "provenance_edges",
    "progress_events",
    "progress_projections",
    "audit_events",
    "close_runs",
    "posting_operations",
    "accounting_periods",
    "approval_actions",
    "approval_requests",
    "policy_decisions",
    "policy_rules",
    "policy_sets",
    "journal_proposal_lines",
    "journal_proposals",
    "exceptions",
    "match_proposal_items",
    "match_proposals",
    "extraction_fields",
    "document_extractions",
    "service_call_attempts",
    "consumer_inbox",
    "outbox_events",
    "job_attempts",
    "processing_jobs",
    "transaction_import_errors",
    "bank_transactions",
    "transaction_imports",
    "document_scan_results",
    "document_versions",
    "documents",
    "idempotency_records",
)


class DemoResetError(RuntimeError):
    pass


def _psycopg_dsn(settings: Settings) -> str:
    assert settings.migration_dsn is not None
    return settings.migration_dsn.get_secret_value().replace(
        "postgresql+psycopg://", "postgresql://", 1
    )


def _require_safe_reset(settings: Settings, *, confirmed: bool, tenant_id: UUID) -> None:
    if settings.environment == "production":
        raise DemoResetError("NOVA demo reset is prohibited in production")
    if not confirmed:
        raise DemoResetError("NOVA demo reset requires explicit confirmation")
    if tenant_id != NOVA_TENANT_ID:
        raise DemoResetError("NOVA demo reset refuses an arbitrary tenant")
    if not settings.migration_dsn:
        raise DemoResetError("the migration DSN is required for the NOVA demo reset")


def _reset_database(settings: Settings) -> dict[str, int]:
    assert settings.migration_dsn is not None
    deleted: dict[str, int] = {}
    with (
        psycopg.connect(_psycopg_dsn(settings)) as connection,
        connection.transaction(),
    ):
        for table in TENANT_TABLES:
            connection.execute(f"ALTER TABLE public.{table} DISABLE TRIGGER USER")
            cursor = connection.execute(
                f"DELETE FROM public.{table} WHERE tenant_id = %s", (NOVA_TENANT_ID,)
            )
            deleted[table] = cursor.rowcount
            connection.execute(f"ALTER TABLE public.{table} ENABLE TRIGGER USER")
    return deleted


def _reset_storage(settings: Settings) -> int:
    if not (
        settings.storage_endpoint_url
        and settings.storage_access_key
        and settings.storage_secret_key
    ):
        raise DemoResetError("configured object storage is required for the NOVA demo")
    client = boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        aws_access_key_id=settings.storage_access_key.get_secret_value(),
        aws_secret_access_key=settings.storage_secret_key.get_secret_value(),
        region_name=settings.storage_region,
        use_ssl=settings.storage_use_tls,
    )
    prefix = f"quarantine/{NOVA_TENANT_ID}/"
    removed = 0
    paginator = client.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=settings.storage_bucket, Prefix=prefix):
        objects = [
            {"Key": item["Key"], "VersionId": item["VersionId"]}
            for group in ("Versions", "DeleteMarkers")
            for item in page.get(group, [])
        ]
        if objects:
            client.delete_objects(Bucket=settings.storage_bucket, Delete={"Objects": objects})
            removed += len(objects)
    return removed


def _reset_redis(settings: Settings) -> int:
    if not settings.redis_url:
        raise DemoResetError("configured Redis is required for the NOVA demo")
    client = redis.Redis.from_url(settings.redis_url.get_secret_value())
    keys = list(client.scan_iter(match="ledgerai:demo:nova:*", count=100))
    return cast(int, client.delete(*keys)) if keys else 0


def _record_reset(settings: Settings, deleted: dict[str, int]) -> UUID:
    assert settings.migration_dsn is not None
    event_id, row_id, correlation_id = uuid4(), uuid4(), uuid4()
    occurred_at = datetime.now(UTC)
    metadata: dict[str, Any] = {
        "scope": "known-nova-tenant-only",
        "tables_cleared": sum(1 for count in deleted.values() if count),
    }
    material = {
        "audit_event_id": str(event_id),
        "tenant_id": str(NOVA_TENANT_ID),
        "actor_id": "ledgerai-demo-reset",
        "action": "DEMO_RESET",
        "resource_type": "tenant",
        "resource_id": str(NOVA_TENANT_ID),
        "resource_version": "nova-phase4-v1",
        "outcome": "SUCCEEDED",
        "correlation_id": str(correlation_id),
        "causation_id": None,
        "metadata": metadata,
        "occurred_at": occurred_at.isoformat(),
        "previous_hash": None,
    }
    event_hash = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    with psycopg.connect(_psycopg_dsn(settings)) as connection:
        connection.execute(
            """
            INSERT INTO audit_events
              (id, tenant_id, organization_id, legal_entity_id, audit_event_id, actor_type,
               actor_id, action, resource_type, resource_id, resource_version, outcome,
               correlation_id, metadata, event_hash, occurred_at)
            VALUES (%s, %s, %s, %s, %s, 'SERVICE', %s, 'DEMO_RESET', 'tenant', %s,
                    'nova-phase4-v1', 'SUCCEEDED', %s, %s::jsonb, %s, %s)
            """,
            (
                row_id,
                NOVA_TENANT_ID,
                NOVA_ORGANIZATION_ID,
                NOVA_ENTITY_ID,
                event_id,
                "ledgerai-demo-reset",
                NOVA_TENANT_ID,
                correlation_id,
                json.dumps(metadata),
                event_hash,
                occurred_at,
            ),
        )
    return event_id


def reset_nova_demo(
    settings: Settings, *, confirmed: bool, tenant_id: UUID = NOVA_TENANT_ID
) -> dict[str, object]:
    """Reset only NOVA business state, then idempotently restore its authorization seed."""
    _require_safe_reset(settings, confirmed=confirmed, tenant_id=tenant_id)
    deleted = _reset_database(settings)
    storage_versions = _reset_storage(settings)
    redis_keys = _reset_redis(settings)
    seed(settings)
    event_id = _record_reset(settings, deleted)
    return {
        "tenant_id": str(NOVA_TENANT_ID),
        "audit_event_id": str(event_id),
        "database_rows": sum(deleted.values()),
        "storage_versions": storage_versions,
        "redis_keys": redis_keys,
    }
