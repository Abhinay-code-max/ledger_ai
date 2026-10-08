"""Add Phase 4 posting assurance, audit, progress, close, and statements."""

from collections.abc import Sequence

from alembic import op

from ledgerai_backend.assurance.models import (
    AccountingPeriod,
    AuditEvent,
    CloseRun,
    FinancialStatementLine,
    FinancialStatementSnapshot,
    PostingConfirmation,
    PostingOperation,
    ProgressEvent,
    ProgressProjection,
    ProvenanceEdge,
)

revision: str = "20261008_04"
down_revision: str | None = "20261007_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    PostingOperation.__table__,
    PostingConfirmation.__table__,
    AccountingPeriod.__table__,
    CloseRun.__table__,
    FinancialStatementSnapshot.__table__,
    FinancialStatementLine.__table__,
    AuditEvent.__table__,
    ProvenanceEdge.__table__,
    ProgressEvent.__table__,
    ProgressProjection.__table__,
)

APPEND_ONLY = {
    "posting_confirmations",
    "financial_statement_snapshots",
    "financial_statement_lines",
    "audit_events",
    "provenance_edges",
    "progress_events",
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
        op.execute(f"GRANT {grants} ON TABLE public.{table.name} TO ledgerai_runtime")

    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("""
        ALTER TABLE public.accounting_periods
        ADD CONSTRAINT ex_accounting_period_no_overlap
        EXCLUDE USING gist (
          tenant_id WITH =,
          legal_entity_id WITH =,
          daterange(period_start, period_end, '[]') WITH &&
        )
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION ledgerai.reject_append_only_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'append-only record cannot be changed' USING ERRCODE = '55000';
        END $$
    """)
    for table_name in sorted(APPEND_ONLY):
        op.execute(
            f"CREATE TRIGGER {table_name}_append_only "
            f"BEFORE UPDATE OR DELETE ON public.{table_name} "
            "FOR EACH ROW EXECUTE FUNCTION ledgerai.reject_append_only_mutation()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
    op.execute("DROP FUNCTION IF EXISTS ledgerai.reject_append_only_mutation() CASCADE")
