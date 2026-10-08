from psycopg import Connection

PHASE4_TABLES = {
    "posting_operations",
    "posting_confirmations",
    "accounting_periods",
    "close_runs",
    "financial_statement_snapshots",
    "financial_statement_lines",
    "audit_events",
    "provenance_edges",
    "progress_events",
    "progress_projections",
}

APPEND_ONLY = {
    "posting_confirmations",
    "financial_statement_snapshots",
    "financial_statement_lines",
    "audit_events",
    "provenance_edges",
    "progress_events",
}


def test_phase4_tables_have_forced_rls(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    rows = admin_connection.execute(
        """SELECT relname, relrowsecurity, relforcerowsecurity
           FROM pg_class WHERE relname = ANY(%s)""",
        (list(PHASE4_TABLES),),
    ).fetchall()
    assert {row[0] for row in rows} == PHASE4_TABLES
    assert all(row[1] and row[2] for row in rows)


def test_append_only_tables_deny_runtime_mutation(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    rows = admin_connection.execute(
        """SELECT table_name, privilege_type FROM information_schema.role_table_grants
           WHERE grantee = 'ledgerai_runtime' AND table_name = ANY(%s)""",
        (list(APPEND_ONLY),),
    ).fetchall()
    privileges: dict[str, set[str]] = {}
    for table, privilege in rows:
        privileges.setdefault(str(table), set()).add(str(privilege))
    assert set(privileges) == APPEND_ONLY
    assert all(values == {"SELECT", "INSERT"} for values in privileges.values())


def test_append_only_triggers_and_period_overlap_constraint_exist(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    triggers = {
        row[0]
        for row in admin_connection.execute(
            """SELECT event_object_table FROM information_schema.triggers
               WHERE trigger_name LIKE '%_append_only'"""
        )
    }
    assert triggers == APPEND_ONLY
    constraint = admin_connection.execute(
        """SELECT contype FROM pg_constraint
           WHERE conname = 'ex_accounting_period_no_overlap'"""
    ).fetchone()
    assert constraint == ("x",)
