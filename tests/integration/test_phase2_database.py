from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest
from phase1_postgres_support import ACME_TENANT
from psycopg import Connection

from ledgerai_backend.database.seed import stable_id

pytestmark = pytest.mark.postgres

PHASE2_TABLES = (
    "documents",
    "document_versions",
    "document_scan_results",
    "transaction_imports",
    "bank_transactions",
    "transaction_import_errors",
    "processing_jobs",
    "job_attempts",
    "outbox_events",
    "consumer_inbox",
    "idempotency_records",
)


def set_tenant(connection: Connection[tuple[object, ...]], tenant_id: object) -> None:
    connection.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))


def test_all_phase2_tables_have_forced_rls_and_runtime_grants(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    rows = admin_connection.execute(
        """SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                  has_table_privilege('ledgerai_runtime', c.oid, 'SELECT,INSERT,UPDATE,DELETE')
             FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname = ANY(%s) ORDER BY c.relname""",
        (list(PHASE2_TABLES),),
    ).fetchall()
    assert len(rows) == len(PHASE2_TABLES)
    assert all(row[1:] == (True, True, True) for row in rows)


@pytest.mark.parametrize("table", PHASE2_TABLES)
def test_phase2_tables_fail_closed_without_context(
    runtime_connection: Connection[tuple[object, ...]], table: str
) -> None:
    assert runtime_connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)


def test_document_rls_rejects_foreign_tenant_write(
    runtime_connection: Connection[tuple[object, ...]],
) -> None:
    set_tenant(runtime_connection, stable_id("nova:tenant"))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        runtime_connection.execute(
            """INSERT INTO documents
               (id,tenant_id,organization_id,legal_entity_id,original_filename,status,
                created_by_principal_id,correlation_id)
               VALUES (%s,%s,%s,%s,'synthetic.pdf','INITIATED',%s,%s)""",
            (uuid4(), ACME_TENANT, uuid4(), uuid4(), uuid4(), uuid4()),
        )
