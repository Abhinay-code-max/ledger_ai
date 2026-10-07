"""Add Phase 3 service integration, policy, exception, and review persistence."""

from collections.abc import Sequence

from alembic import op

from ledgerai_backend.integration.models import (
    ApprovalAction,
    ApprovalRequest,
    DocumentExtraction,
    ExtractionField,
    JournalProposal,
    JournalProposalLine,
    MatchProposal,
    MatchProposalItem,
    PolicyDecision,
    PolicyRule,
    PolicySet,
    ServiceCallAttempt,
    WorkflowException,
)

revision: str = "20261007_03"
down_revision: str | None = "20261006_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    DocumentExtraction.__table__,
    ExtractionField.__table__,
    MatchProposal.__table__,
    MatchProposalItem.__table__,
    WorkflowException.__table__,
    JournalProposal.__table__,
    JournalProposalLine.__table__,
    PolicySet.__table__,
    PolicyRule.__table__,
    PolicyDecision.__table__,
    ApprovalRequest.__table__,
    ApprovalAction.__table__,
    ServiceCallAttempt.__table__,
)

IMMUTABLE_TABLES = {
    "document_extractions",
    "extraction_fields",
    "match_proposals",
    "match_proposal_items",
    "journal_proposals",
    "journal_proposal_lines",
    "policy_rules",
    "policy_decisions",
    "approval_actions",
    "service_call_attempts",
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
        grants = "SELECT, INSERT" if table.name in IMMUTABLE_TABLES else "SELECT, INSERT, UPDATE"
        op.execute(f"GRANT {grants} ON TABLE public.{table.name} TO ledgerai_runtime")

    # Published policy versions become immutable. Drafts can be edited only before publication.
    op.execute("""
        CREATE OR REPLACE FUNCTION ledgerai.reject_published_policy_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.published_at IS NOT NULL THEN
            RAISE EXCEPTION 'published policy sets are immutable' USING ERRCODE = '55000';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER policy_sets_immutable_after_publish
        BEFORE UPDATE OR DELETE ON public.policy_sets
        FOR EACH ROW EXECUTE FUNCTION ledgerai.reject_published_policy_mutation()
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_outbox_posting_request_resource
        ON public.outbox_events (
          tenant_id,
          event_type,
          (payload_reference->>'resource_type'),
          (payload_reference->>'resource_id')
        )
        WHERE event_type = 'journal.posting.requested.v1'
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_processing_jobs_phase3_input
        ON public.processing_jobs (tenant_id, job_type, input_reference)
        WHERE job_type IN ('DOCUMENT_EXTRACTION', 'RECONCILIATION')
    """)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP INDEX IF EXISTS public.uq_outbox_posting_request_resource")
    op.execute("DROP INDEX IF EXISTS public.uq_processing_jobs_phase3_input")
    op.execute("DROP FUNCTION IF EXISTS ledgerai.reject_published_policy_mutation() CASCADE")
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
