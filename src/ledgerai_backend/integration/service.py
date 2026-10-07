"""Race-safe version-bound approval and posting-request workflow."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

from ledgerai_backend.core.errors import ApiError
from ledgerai_backend.core.observability import (
    approval_actions,
    posting_request_deduplications,
    stale_approval_rejections,
)
from ledgerai_backend.core.request_context import AuthorizationContext
from ledgerai_backend.integration.models import (
    ApprovalAction,
    ApprovalActionType,
    ApprovalRequest,
    ApprovalStatus,
    JournalProposal,
    JournalProposalLine,
    PolicyDecision,
    PolicyOutcome,
)
from ledgerai_backend.integration.policy import PolicyRuleSpec, evaluate_policy
from ledgerai_backend.integration.repository import IntegrationRepository
from ledgerai_backend.integration.schemas import ApprovalActionRequest
from ledgerai_contracts.v1.journals import JournalProposal as JournalContract

_STATUS = {
    ApprovalActionType.APPROVE: ApprovalStatus.APPROVED,
    ApprovalActionType.CORRECT: ApprovalStatus.CORRECTED,
    ApprovalActionType.REJECT: ApprovalStatus.REJECTED,
    ApprovalActionType.REQUEST_EVIDENCE: ApprovalStatus.EVIDENCE_REQUESTED,
    ApprovalActionType.ESCALATE: ApprovalStatus.ESCALATED,
}
_REASON_REQUIRED = {
    ApprovalActionType.CORRECT,
    ApprovalActionType.REJECT,
    ApprovalActionType.REQUEST_EVIDENCE,
    ApprovalActionType.ESCALATE,
}


class ApprovalService:
    def __init__(self, repository: IntegrationRepository, context: AuthorizationContext) -> None:
        self.repository, self.context = repository, context

    async def act(
        self,
        request_id: UUID,
        action_type: ApprovalActionType,
        body: ApprovalActionRequest,
        *,
        idempotency_key: str,
        expected_version: int,
    ) -> ApprovalAction:
        duplicate = await self.repository.existing_action(
            actor_id=self.context.principal_id, idempotency_key=idempotency_key
        )
        if duplicate:
            if duplicate.approval_request_id != request_id or duplicate.action != action_type:
                raise ApiError(
                    409,
                    "CONFLICT",
                    "IDEMPOTENCY_CONFLICT",
                    "Idempotency key conflicts with another action.",
                )
            if action_type == ApprovalActionType.APPROVE:
                posting_request_deduplications.add(1)
            return duplicate
        request = await self.repository.lock_approval(request_id)
        if request is None:
            raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
        if request.version != expected_version:
            stale_approval_rejections.add(1, {"reason": "request_version"})
            raise ApiError(409, "CONFLICT", "STALE_APPROVAL", "The approval request has changed.")
        if self.repository.expired(request):
            request.status = ApprovalStatus.EXPIRED
            request.version += 1
            raise ApiError(409, "CONFLICT", "APPROVAL_EXPIRED", "The approval request has expired.")
        if self.repository.terminal(request.status):
            raise ApiError(
                409,
                "CONFLICT",
                "APPROVAL_ALREADY_DECIDED",
                "The approval request is already decided.",
            )
        if body.reviewed_resource_version != request.subject_version:
            stale_approval_rejections.add(1, {"reason": "resource_version"})
            raise ApiError(
                409, "CONFLICT", "STALE_RESOURCE_VERSION", "The reviewed resource version is stale."
            )
        if action_type in _REASON_REQUIRED and not body.reason:
            raise ApiError(
                422, "INPUT_VALIDATION", "REASON_REQUIRED", "A reason is required for this action."
            )
        if action_type == ApprovalActionType.CORRECT and not body.structured_corrections:
            raise ApiError(
                422,
                "INPUT_VALIDATION",
                "CORRECTIONS_REQUIRED",
                "Structured corrections are required.",
            )
        if action_type != ApprovalActionType.CORRECT and body.structured_corrections is not None:
            raise ApiError(
                422,
                "INPUT_VALIDATION",
                "CORRECTIONS_NOT_ALLOWED",
                "Corrections are allowed only for correct actions.",
            )
        if (
            request.maker_checker_required
            and request.maker_principal_id == self.context.principal_id
        ):
            raise ApiError(
                403,
                "AUTHORIZATION",
                "MAKER_CHECKER_VIOLATION",
                "The maker cannot review this proposal.",
            )
        row = ApprovalAction(
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
            approval_request_id=request.id,
            reviewed_resource_type=request.subject_type,
            reviewed_resource_id=request.subject_id,
            reviewed_resource_version=request.subject_version,
            action=action_type,
            actor_principal_id=self.context.principal_id,
            actor_roles=sorted(self.context.roles),
            idempotency_key=idempotency_key,
            reason=body.reason,
            structured_corrections=body.structured_corrections,
            separation_of_duties_checked=True,
            correlation_id=UUID(self.context.correlation_id),
        )
        self.repository.session.add(row)
        await self.repository.session.flush()
        request.status = _STATUS[action_type]
        request.terminal_action_id = row.id
        request.version += 1
        request.updated_at = datetime.now(UTC)
        self.repository.add_outbox(
            event_type="approval.decided.v1",
            resource_type="approval_action",
            resource_id=row.id,
            correlation_id=UUID(self.context.correlation_id),
        )
        approval_actions.add(1, {"action": action_type.value})
        if action_type == ApprovalActionType.APPROVE:
            await self._request_posting(request)
        elif action_type == ApprovalActionType.CORRECT:
            await self._create_corrected_version(request, body)
        return row

    async def _create_corrected_version(
        self, request: ApprovalRequest, body: ApprovalActionRequest
    ) -> JournalProposal:
        proposal = await self.repository.journal(request.subject_id)
        old_decision = await self.repository.policy_decision(request.policy_decision_id)
        if proposal is None or old_decision is None or not body.structured_corrections:
            raise ApiError(
                409,
                "CONFLICT",
                "CORRECTION_PRECONDITION_FAILED",
                "The proposal cannot be corrected from the current evidence.",
            )
        payload = deepcopy(proposal.contract_payload)
        payload.update(body.structured_corrections)
        payload["proposal_version"] = proposal.proposal_version + 1
        payload["policy_decision"] = None
        payload["approval_decision"] = None
        try:
            contract = JournalContract.model_validate(payload)
        except ValueError as exc:
            raise ApiError(
                422,
                "INPUT_VALIDATION",
                "INVALID_CORRECTION",
                "The corrected proposal does not satisfy the journal contract.",
            ) from exc
        corrected = JournalProposal(
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
            proposal_series_id=proposal.proposal_series_id,
            proposal_version=contract.proposal_version,
            proposed_journal_date=contract.proposed_journal_date,
            currency=contract.currency,
            explanation=contract.explanation,
            accounting_validation="NOT_VALIDATED",
            posting_status="UNPOSTED",
            producer_name="ledgerai-human-correction",
            producer_version="1.0",
            contract_payload=contract.model_dump(mode="json"),
            created_by_principal_id=self.context.principal_id,
            correlation_id=UUID(self.context.correlation_id),
        )
        self.repository.session.add(corrected)
        await self.repository.session.flush()
        for line in contract.lines:
            self.repository.session.add(
                JournalProposalLine(
                    tenant_id=self.repository.tenant_id,
                    organization_id=self.repository.organization_id,
                    legal_entity_id=self.repository.legal_entity_id,
                    journal_proposal_id=corrected.id,
                    line_id=line.line_id,
                    account_reference=line.account_reference,
                    direction=line.direction,
                    amount=line.amount.amount,
                    currency=line.amount.currency,
                    description=line.description,
                    source_evidence=[item.model_dump(mode="json") for item in line.source_evidence],
                )
            )
        stored_rules = await self.repository.policy_rules(old_decision.policy_set_id)
        rule_specs = [
            PolicyRuleSpec.model_validate(
                {
                    "rule_id": rule.rule_id,
                    "priority": rule.priority,
                    "conditions": rule.conditions,
                    "outcome": rule.outcome.value,
                    "reason_code": rule.reason_code,
                    "explanation": rule.explanation,
                }
            )
            for rule in stored_rules
        ]
        replay = evaluate_policy(old_decision.evaluated_inputs, rule_specs)  # type: ignore[arg-type]
        decision = PolicyDecision(
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
            subject_type="journal_proposal",
            subject_id=corrected.id,
            subject_version=str(corrected.proposal_version),
            policy_set_id=old_decision.policy_set_id,
            policy_set_version=old_decision.policy_set_version,
            outcome=replay.outcome,
            evaluated_inputs=old_decision.evaluated_inputs,
            matched_rule_ids=list(replay.matched_rule_ids),
            reason_codes=list(replay.reason_codes),
            explanation=replay.explanation,
            evaluator_version="1.0",
            correlation_id=UUID(self.context.correlation_id),
        )
        self.repository.session.add(decision)
        await self.repository.session.flush()
        next_request = ApprovalRequest(
            tenant_id=self.repository.tenant_id,
            organization_id=self.repository.organization_id,
            legal_entity_id=self.repository.legal_entity_id,
            subject_type="journal_proposal",
            subject_id=corrected.id,
            subject_version=str(corrected.proposal_version),
            policy_decision_id=decision.id,
            maker_principal_id=self.context.principal_id,
            maker_checker_required=request.maker_checker_required,
            expires_at=datetime.now(UTC) + (request.expires_at - request.created_at),
            correlation_id=UUID(self.context.correlation_id),
        )
        self.repository.session.add(next_request)
        await self.repository.session.flush()
        for event_type, resource_type, resource_id in (
            ("journal.proposal.created.v1", "journal_proposal", corrected.id),
            ("policy.evaluated.v1", "policy_decision", decision.id),
            ("approval.requested.v1", "approval_request", next_request.id),
        ):
            self.repository.add_outbox(
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=UUID(self.context.correlation_id),
            )
        return corrected

    async def _request_posting(self, request: ApprovalRequest) -> None:
        decision = await self.repository.policy_decision(request.policy_decision_id)
        proposal = await self.repository.journal(request.subject_id)
        if decision is None or proposal is None:
            raise ApiError(
                409,
                "CONFLICT",
                "POSTING_PRECONDITION_FAILED",
                "Required decision evidence is unavailable.",
            )
        if decision.outcome not in {PolicyOutcome.AUTO_ELIGIBLE, PolicyOutcome.REVIEW_REQUIRED}:
            raise ApiError(
                409, "CONFLICT", "POLICY_BLOCKS_POSTING", "Policy does not permit posting handoff."
            )
        if str(
            proposal.proposal_version
        ) != request.subject_version or await self.repository.has_newer_journal_version(proposal):
            raise ApiError(
                409, "CONFLICT", "STALE_RESOURCE_VERSION", "The proposal version is stale."
            )
        if (
            proposal.accounting_validation != "NOT_VALIDATED"
            or proposal.posting_status != "UNPOSTED"
        ):
            raise ApiError(
                409,
                "CONFLICT",
                "INVALID_PROPOSAL_STATE",
                "The proposal is not eligible for posting handoff.",
            )
        if await self.repository.has_blocking_exception():
            raise ApiError(
                409,
                "CONFLICT",
                "BLOCKING_EXCEPTION",
                "A blocking exception must be resolved first.",
            )
        self.repository.add_outbox(
            event_type="journal.posting.requested.v1",
            resource_type="journal_proposal",
            resource_id=proposal.id,
            correlation_id=UUID(self.context.correlation_id),
            causation_id=request.terminal_action_id,
        )
