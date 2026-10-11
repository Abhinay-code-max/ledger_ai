"""Create Role 2 deterministic accounting core tables, RLS, and append-only immutability triggers."""

from collections.abc import Sequence

from alembic import op

from ledgerai_role2.database.models import (
    Role2Account,
    Role2AccountingPeriod,
    Role2JournalLine,
    Role2PeriodCloseOperation,
    Role2PostedJournal,
    Role2PostingOperation,
    Role2ProposalRecord,
    Role2StatementLine,
    Role2StatementSnapshot,
)

revision: str = "20261011_05"
down_revision: str | None = "20261008_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    Role2Account.__table__,
    Role2AccountingPeriod.__table__,
    Role2PostingOperation.__table__,
    Role2PostedJournal.__table__,
    Role2JournalLine.__table__,
    Role2PeriodCloseOperation.__table__,
    Role2StatementSnapshot.__table__,
    Role2StatementLine.__table__,
    Role2ProposalRecord.__table__,
)

APPEND_ONLY = {
    "role2_posted_journals",
    "role2_journal_lines",
    "role2_statement_snapshots",
    "role2_statement_lines",
}


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)
        op.execute(f"ALTER TABLE public.{table.name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table.name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table.name}_tenant_isolation ON public.{table.name} "
            "USING (tenant_id = ledgerai.current_tenant_id()) "
            "WITH CHECK (tenant_id = ledgerai.current_tenant_id())"
        )
        grants = "SELECT, INSERT" if table.name in APPEND_ONLY else "SELECT, INSERT, UPDATE"
        # Grant to runtime role if it exists in Postgres
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'ledgerai_runtime') THEN
                    GRANT {grants} ON TABLE public.{table.name} TO ledgerai_runtime;
                END IF;
            END
            $$;
        """)

    # Attach append-only immutability trigger
    for table_name in sorted(APPEND_ONLY):
        op.execute(
            f"CREATE TRIGGER {table_name}_append_only "
            f"BEFORE UPDATE OR DELETE ON public.{table_name} "
            "FOR EACH ROW EXECUTE FUNCTION ledgerai.reject_append_only_mutation()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in sorted(APPEND_ONLY):
        op.execute(f"DROP TRIGGER IF EXISTS {table_name}_append_only ON public.{table_name}")

    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
