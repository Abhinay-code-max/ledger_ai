from phase1_postgres_support import ACME_TENANT
from psycopg import Connection

PHASE3_TABLES = {
    "document_extractions",
    "extraction_fields",
    "match_proposals",
    "match_proposal_items",
    "exceptions",
    "journal_proposals",
    "journal_proposal_lines",
    "policy_sets",
    "policy_rules",
    "policy_decisions",
    "approval_requests",
    "approval_actions",
    "service_call_attempts",
}

IMMUTABLE_TABLES = PHASE3_TABLES - {"exceptions", "policy_sets", "approval_requests"}


def test_phase3_tables_have_forced_rls(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    rows = admin_connection.execute(
        """SELECT relname, relrowsecurity, relforcerowsecurity
           FROM pg_class WHERE relname = ANY(%s)""",
        (list(PHASE3_TABLES),),
    ).fetchall()
    assert {row[0] for row in rows} == PHASE3_TABLES
    assert all(row[1] and row[2] for row in rows)


def test_runtime_can_select_only_inside_tenant_context(
    runtime_connection: Connection[tuple[object, ...]],
) -> None:
    runtime_connection.execute(
        "SELECT set_config('ledgerai.tenant_id', %s, true)", (str(ACME_TENANT),)
    )
    for table in sorted(PHASE3_TABLES):
        runtime_connection.execute(f"SELECT count(*) FROM public.{table}").fetchone()


def test_immutable_tables_deny_runtime_update_and_delete(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    rows = admin_connection.execute(
        """SELECT table_name, privilege_type FROM information_schema.role_table_grants
           WHERE grantee = 'ledgerai_runtime' AND table_name = ANY(%s)""",
        (list(IMMUTABLE_TABLES),),
    ).fetchall()
    privileges: dict[str, set[str]] = {}
    for table, privilege in rows:
        privileges.setdefault(str(table), set()).add(str(privilege))
    assert set(privileges) == IMMUTABLE_TABLES
    assert all(values == {"SELECT", "INSERT"} for values in privileges.values())


def test_posting_and_job_idempotency_indexes_exist(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    names = {
        row[0]
        for row in admin_connection.execute(
            "SELECT indexname FROM pg_indexes WHERE indexname = ANY(%s)",
            (["uq_outbox_posting_request_resource", "uq_processing_jobs_phase3_input"],),
        )
    }
    assert names == {"uq_outbox_posting_request_resource", "uq_processing_jobs_phase3_input"}
