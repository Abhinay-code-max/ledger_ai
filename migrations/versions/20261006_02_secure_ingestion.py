"""Create the Phase 2 secure ingestion and asynchronous workflow foundation."""

from collections.abc import Sequence

from alembic import op

from ledgerai_backend.ingestion.models import (
    BankTransaction,
    ConsumerInbox,
    Document,
    DocumentScanResult,
    DocumentVersion,
    IdempotencyRecord,
    JobAttempt,
    OutboxEvent,
    ProcessingJob,
    TransactionImport,
    TransactionImportError,
)

revision: str = "20261006_02"
down_revision: str | None = "20261006_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    Document.__table__,
    DocumentVersion.__table__,
    DocumentScanResult.__table__,
    TransactionImport.__table__,
    BankTransaction.__table__,
    TransactionImportError.__table__,
    ProcessingJob.__table__,
    JobAttempt.__table__,
    OutboxEvent.__table__,
    ConsumerInbox.__table__,
    IdempotencyRecord.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        # The published Phase 1 migration calls Base.metadata.create_all(). When
        # Alembic loads this forward revision during a clean upgrade, these new
        # models are therefore already present in the shared metadata. Preserve
        # that published revision and make this revision safe in both paths:
        # existing Phase 1 databases create the tables here; clean databases
        # continue by applying the Phase 2 security policy and grants below.
        table.create(bind=bind, checkfirst=True)
        op.execute(f"ALTER TABLE public.{table.name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table.name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table.name}_tenant_isolation ON public.{table.name}
            USING (tenant_id = ledgerai.current_tenant_id())
            WITH CHECK (tenant_id = ledgerai.current_tenant_id())
            """
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{table.name} TO ledgerai_runtime"
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind)
