"""Idempotent Phase 3 workflow persistence at external-service boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from ledgerai_backend.core.observability import (
    exception_creations,
    policy_outcomes,
    reconciliation_outcomes,
)
from ledgerai_backend.ingestion.models import (
    DocumentStatus,
    DocumentVersion,
    JobStatus,
    ProcessingJob,
)
from ledgerai_backend.integration.adapters import ReconciliationResult
from ledgerai_backend.integration.models import (
    ApprovalRequest,
    ExceptionResolution,
    ExtractionField,
    ExtractionStatus,
    JournalProposalLine,
    MatchProposalItem,
    PolicyOutcome,
    ProposalStatus,
    ValidationOutcome,
    WorkflowException,
)
from ledgerai_backend.integration.models import (
    DocumentExtraction as ExtractionRow,
)
from ledgerai_backend.integration.models import (
    JournalProposal as JournalRow,
)
from ledgerai_backend.integration.models import (
    MatchProposal as MatchRow,
)
from ledgerai_backend.integration.models import (
    PolicyDecision as PolicyDecisionRow,
)
from ledgerai_backend.integration.policy import PolicyRuleSpec, evaluate_policy
from ledgerai_backend.integration.repository import IntegrationRepository
from ledgerai_backend.integration.validation import validate_extraction
from ledgerai_contracts.v1.documents import DocumentExtraction
from ledgerai_contracts.v1.journals import JournalProposal
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class WorkflowContractError(ValueError):
    pass


class WorkflowOrchestrator:
    def __init__(self, repository: IntegrationRepository, *, correlation_id: UUID) -> None:
        self.repository, self.correlation_id = repository, correlation_id
        self.context = EntityTenantContext(
            tenant_id=repository.tenant_id,
            organization_id=repository.organization_id,
            legal_entity_id=repository.legal_entity_id,
        )

    async def ensure_extraction_job(
        self, version_id: UUID, *, maximum_attempts: int = 5
    ) -> ProcessingJob:
        version = await self.repository.session.scalar(
            select(DocumentVersion)
            .where(
                DocumentVersion.tenant_id == self.repository.tenant_id,
                DocumentVersion.organization_id == self.repository.organization_id,
                DocumentVersion.legal_entity_id == self.repository.legal_entity_id,
                DocumentVersion.id == version_id,
            )
            .with_for_update()
        )
        if version is None or version.status != DocumentStatus.ACCEPTED:
            raise WorkflowContractError(
                "only an accepted immutable document version can be extracted"
            )
        reference = f"document_version:{version.id}"
        existing = await self.repository.session.scalar(
            select(ProcessingJob).where(
                ProcessingJob.tenant_id == self.repository.tenant_id,
                ProcessingJob.job_type == "DOCUMENT_EXTRACTION",
                ProcessingJob.input_reference == reference,
            )
        )
        if existing:
            return existing
        job = ProcessingJob(
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
            job_type="DOCUMENT_EXTRACTION",
            handler_version="3.0",
            status=JobStatus.QUEUED,
            maximum_attempts=maximum_attempts,
            input_reference=reference,
            queue_name="ledgerai.workflow",
            correlation_id=self.correlation_id,
        )
        self.repository.session.add(job)
        await self.repository.session.flush()
        self.repository.add_outbox(
            event_type="document.extraction.requested.v1",
            resource_type="processing_job",
            resource_id=job.id,
            correlation_id=self.correlation_id,
        )
        return job

    async def persist_extraction(
        self, contract: DocumentExtraction, *, document_version_id: UUID, producer_result_id: str
    ) -> ExtractionRow:
        if contract.tenant_context != self.context:
            raise WorkflowContractError("extraction tenant context mismatch")
        version = await self.repository.session.scalar(
            select(DocumentVersion).where(
                DocumentVersion.tenant_id == self.repository.tenant_id,
                DocumentVersion.id == document_version_id,
                DocumentVersion.document_id == contract.document_id,
            )
        )
        if version is None or str(version.version_number) != contract.document_version:
            raise WorkflowContractError("extraction document version mismatch")
        result = validate_extraction(contract)
        next_version = (
            int(
                await self.repository.session.scalar(
                    select(func.coalesce(func.max(ExtractionRow.extraction_version), 0)).where(
                        ExtractionRow.tenant_id == self.repository.tenant_id,
                        ExtractionRow.document_version_id == document_version_id,
                    )
                )
                or 0
            )
            + 1
        )
        row = ExtractionRow(
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
            document_id=contract.document_id,
            document_version_id=document_version_id,
            extraction_version=next_version,
            producer_result_id=producer_result_id,
            schema_version=contract.schema_version,
            producer_name=contract.producer.name,
            producer_version=contract.producer.version,
            model_name=contract.producer.model_name,
            model_version=contract.producer.model_version,
            prompt_template_version=contract.producer.prompt_template_version,
            status=ExtractionStatus(contract.status),
            review_disposition=contract.review_disposition,
            validation_outcome=ValidationOutcome(result.outcome),
            contract_payload=contract.model_dump(mode="json"),
            correlation_id=self.correlation_id,
        )
        self.repository.session.add(row)
        await self.repository.session.flush()
        for field in contract.fields:
            self.repository.session.add(
                ExtractionField(
                    tenant_id=self.repository.tenant_id,
                    organization_id=self.repository.organization_id,
                    legal_entity_id=self.repository.legal_entity_id,
                    extraction_id=row.id,
                    field_name=field.field_name,
                    is_critical=field.is_critical,
                    state=field.state,
                    value_json={"value": field.model_dump(mode="json")["value"]}
                    if field.value is not None
                    else None,
                    confidence=field.confidence,
                    provenance=[item.model_dump(mode="json") for item in field.provenance],
                )
            )
        self.repository.add_outbox(
            event_type="document.extracted.v1",
            resource_type="document_extraction",
            resource_id=row.id,
            correlation_id=self.correlation_id,
        )
        if result.outcome == "VALIDATED":
            self.repository.add_outbox(
                event_type="document.validated.v1",
                resource_type="document_extraction",
                resource_id=row.id,
                correlation_id=self.correlation_id,
            )
        return row

    async def persist_reconciliation(
        self, result: ReconciliationResult, *, allowed_resource_ids: set[UUID]
    ) -> tuple[MatchRow, list[WorkflowException]]:
        if result.tenant_context != self.context or result.proposal.tenant_context != self.context:
            raise WorkflowContractError("reconciliation tenant context mismatch")
        unknown = {reference.resource_id for reference in result.proposal.records}.difference(
            allowed_resource_ids
        )
        if unknown:
            raise WorkflowContractError("reconciliation references an unknown or foreign resource")
        if not result.proposal.producer.algorithm_version:
            raise WorkflowContractError("reconciliation algorithm version is required")
        proposal = result.proposal

        existing_match = await self.repository.session.scalar(
            select(MatchRow).where(
                MatchRow.tenant_id == self.repository.tenant_id,
                MatchRow.external_proposal_id == proposal.proposal_id,
                MatchRow.proposal_version == proposal.proposal_version,
            )
        )
        if existing_match is not None:
            row = existing_match
        else:
            row = MatchRow(
                tenant_id=self.repository.tenant_id,
                organization_id=self.repository.organization_id,
                legal_entity_id=self.repository.legal_entity_id,
                external_proposal_id=proposal.proposal_id,
                proposal_version=proposal.proposal_version,
                match_type=proposal.match_type,
                confidence=proposal.confidence,
                status=ProposalStatus(proposal.status),
                producer_name=proposal.producer.name,
                producer_version=proposal.producer.version,
                algorithm_version=proposal.producer.algorithm_version,
                contract_payload=proposal.model_dump(mode="json"),
                correlation_id=self.correlation_id,
            )
            self.repository.session.add(row)
            await self.repository.session.flush()
            for reference in proposal.records:
                self.repository.session.add(
                    MatchProposalItem(
                        tenant_id=self.repository.tenant_id,
                        organization_id=self.repository.organization_id,
                        legal_entity_id=self.repository.legal_entity_id,
                        match_proposal_id=row.id,
                        resource_type=reference.resource_type,
                        resource_id=reference.resource_id,
                        resource_version=reference.resource_version,
                    )
                )
            self.repository.add_outbox(
                event_type="reconciliation.proposed.v1",
                resource_type="match_proposal",
                resource_id=row.id,
                correlation_id=self.correlation_id,
            )
            reconciliation_outcomes.add(1, {"outcome": proposal.status})

        persisted_exceptions: list[WorkflowException] = []
        for exception in result.exceptions:
            if exception.tenant_context != self.context or any(
                ref.resource_id not in allowed_resource_ids for ref in exception.involved_resources
            ):
                raise WorkflowContractError("exception references an unknown or foreign resource")

            existing_exc = await self.repository.session.scalar(
                select(WorkflowException).where(
                    WorkflowException.tenant_id == self.repository.tenant_id,
                    WorkflowException.external_exception_id == exception.exception_id,
                )
            )
            if existing_exc is not None:
                persisted_exceptions.append(existing_exc)
                continue

            exception_row = WorkflowException(
                tenant_id=self.repository.tenant_id,
                organization_id=self.repository.organization_id,
                legal_entity_id=self.repository.legal_entity_id,
                external_exception_id=exception.exception_id,
                exception_type=exception.exception_type,
                severity=exception.severity,
                explanation=exception.explanation,
                reason_codes=exception.reason_codes,
                resolution_status=ExceptionResolution(exception.resolution_status),
                resolution_reference=exception.resolution_reference.model_dump(mode="json")
                if exception.resolution_reference
                else None,
                contract_payload=exception.model_dump(mode="json"),
                correlation_id=self.correlation_id,
            )
            self.repository.session.add(exception_row)
            await self.repository.session.flush()
            self.repository.add_outbox(
                event_type="exception.created.v1",
                resource_type="exception",
                resource_id=exception_row.id,
                correlation_id=self.correlation_id,
            )
            exception_creations.add(1, {"severity": exception.severity})
            persisted_exceptions.append(exception_row)
        return row, persisted_exceptions

    async def persist_journal(
        self, proposal: JournalProposal, *, maker_principal_id: UUID | None = None
    ) -> JournalRow:
        if proposal.tenant_context != self.context:
            raise WorkflowContractError("journal tenant context mismatch")
        currencies = {line.amount.currency for line in proposal.lines}
        if currencies != {proposal.currency}:
            raise WorkflowContractError("journal line currency mismatch")

        existing_journal = await self.repository.session.scalar(
            select(JournalRow).where(
                JournalRow.tenant_id == self.repository.tenant_id,
                JournalRow.proposal_series_id == proposal.proposal_id,
                JournalRow.proposal_version == proposal.proposal_version,
            )
        )
        if existing_journal is not None:
            return existing_journal

        row = JournalRow(
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
            proposal_series_id=proposal.proposal_id,
            proposal_version=proposal.proposal_version,
            proposed_journal_date=proposal.proposed_journal_date,
            currency=proposal.currency,
            explanation=proposal.explanation,
            accounting_validation=proposal.accounting_validation,
            posting_status=proposal.posting_status,
            producer_name=proposal.producer.name,
            producer_version=proposal.producer.version,
            contract_payload=proposal.model_dump(mode="json"),
            created_by_principal_id=maker_principal_id,
            correlation_id=self.correlation_id,
        )
        self.repository.session.add(row)
        await self.repository.session.flush()
        for line in proposal.lines:
            self.repository.session.add(
                JournalProposalLine(
                    tenant_id=self.repository.tenant_id,
                    organization_id=self.repository.organization_id,
                    legal_entity_id=self.repository.legal_entity_id,
                    journal_proposal_id=row.id,
                    line_id=line.line_id,
                    account_reference=line.account_reference,
                    direction=line.direction,
                    amount=line.amount.amount,
                    currency=line.amount.currency,
                    description=line.description,
                    source_evidence=[item.model_dump(mode="json") for item in line.source_evidence],
                )
            )
        self.repository.add_outbox(
            event_type="journal.proposal.created.v1",
            resource_type="journal_proposal",
            resource_id=row.id,
            correlation_id=self.correlation_id,
        )
        return row

    async def apply_policy(
        self,
        proposal: JournalRow,
        *,
        policy_set_id: UUID,
        policy_version: str,
        inputs: dict[str, object],
        rules: list[PolicyRuleSpec],
        maker_checker_required: bool = True,
    ) -> PolicyDecisionRow:
        existing_decision = await self.repository.session.scalar(
            select(PolicyDecisionRow).where(
                PolicyDecisionRow.tenant_id == self.repository.tenant_id,
                PolicyDecisionRow.subject_type == "journal_proposal",
                PolicyDecisionRow.subject_id == proposal.id,
                PolicyDecisionRow.subject_version == str(proposal.proposal_version),
                PolicyDecisionRow.policy_set_id == policy_set_id,
            )
        )
        if existing_decision is not None:
            return existing_decision

        evaluation = evaluate_policy(inputs, rules)  # type: ignore[arg-type]
        json_safe_inputs: dict[str, object] = {
            k: str(v) if isinstance(v, (Decimal, UUID)) else v for k, v in inputs.items()
        }
        decision = PolicyDecisionRow(
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
            subject_type="journal_proposal",
            subject_id=proposal.id,
            subject_version=str(proposal.proposal_version),
            policy_set_id=policy_set_id,
            policy_set_version=policy_version,
            outcome=PolicyOutcome(evaluation.outcome),
            evaluated_inputs=json_safe_inputs,
            matched_rule_ids=list(evaluation.matched_rule_ids),
            reason_codes=list(evaluation.reason_codes),
            explanation=evaluation.explanation,
            evaluator_version="1.0",
            correlation_id=self.correlation_id,
        )
        self.repository.session.add(decision)
        await self.repository.session.flush()
        self.repository.add_outbox(
            event_type="policy.evaluated.v1",
            resource_type="policy_decision",
            resource_id=decision.id,
            correlation_id=self.correlation_id,
        )
        policy_outcomes.add(
            1, {"outcome": decision.outcome.value, "policy_version": policy_version}
        )
        if decision.outcome in {PolicyOutcome.REVIEW_REQUIRED, PolicyOutcome.ESCALATED}:
            existing_request = await self.repository.session.scalar(
                select(ApprovalRequest).where(
                    ApprovalRequest.tenant_id == self.repository.tenant_id,
                    ApprovalRequest.subject_type == "journal_proposal",
                    ApprovalRequest.subject_id == proposal.id,
                    ApprovalRequest.subject_version == str(proposal.proposal_version),
                )
            )
            if existing_request is None:
                request = ApprovalRequest(
                    tenant_id=self.repository.tenant_id,
                    organization_id=self.repository.organization_id,
                    legal_entity_id=self.repository.legal_entity_id,
                    subject_type="journal_proposal",
                    subject_id=proposal.id,
                    subject_version=str(proposal.proposal_version),
                    policy_decision_id=decision.id,
                    maker_principal_id=proposal.created_by_principal_id,
                    maker_checker_required=maker_checker_required,
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                    correlation_id=self.correlation_id,
                )
                self.repository.session.add(request)
                await self.repository.session.flush()
                self.repository.add_outbox(
                    event_type="approval.requested.v1",
                    resource_type="approval_request",
                    resource_id=request.id,
                    correlation_id=self.correlation_id,
                )
        return decision
