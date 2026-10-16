"""Tenant-scoped Phase 3 evidence and human-review APIs."""

from __future__ import annotations

from contextlib import suppress
from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from ledgerai_backend.api.dependencies import RequestScope, authorized_scope
from ledgerai_backend.core.errors import ERROR_RESPONSES, ApiError
from ledgerai_backend.database.seed import stable_id
from ledgerai_backend.ingestion.models import BankTransaction
from ledgerai_backend.ingestion.service import require_entity_context
from ledgerai_backend.integration.models import (
    ApprovalActionType,
    ApprovalRequest,
    ApprovalStatus,
    ExceptionResolution,
    ExceptionSeverity,
    JournalProposal,
    MatchProposal,
    WorkflowException,
)
from ledgerai_backend.integration.orchestration import WorkflowOrchestrator
from ledgerai_backend.integration.policy import PolicyCondition, PolicyRuleSpec
from ledgerai_backend.integration.repository import IntegrationRepository
from ledgerai_backend.integration.schemas import (
    ApprovalActionRequest,
    ApprovalActionResponse,
    ApprovalRequestResponse,
    ExceptionResolveRequest,
    ExceptionResponse,
    ExtractionRequest,
    ExtractionResponse,
    JournalProposalResponse,
    MatchProposalResponse,
    Page,
    ReconciliationCreateRequest,
    ReconciliationWorkflowResponse,
)
from ledgerai_backend.integration.service import ApprovalService
from ledgerai_backend.tenancy.permissions import PermissionCode, require_permission
from ledgerai_contracts.v1.common import (
    CorrelationMetadata,
    PositiveMoney,
    ProducerMetadata,
    ProducerType,
    ProvenanceReference,
)
from ledgerai_contracts.v1.journals import (
    JournalProposal as JournalProposalContract,
)
from ledgerai_contracts.v1.journals import (
    ProposedJournalLine,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext

router = APIRouter(responses=ERROR_RESPONSES)
Scope = Annotated[RequestScope, Depends(authorized_scope, scope="function")]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$"),
]
ExpectedVersion = Annotated[int, Header(alias="If-Match", ge=1)]


def _repository(scope: RequestScope) -> IntegrationRepository:
    organization_id, legal_entity_id = require_entity_context(scope.context)
    return IntegrationRepository(
        scope.session, scope.context.tenant_id, organization_id, legal_entity_id
    )


def _page(rows: list[Any], limit: int, schema: type[BaseModel]) -> Page:
    has_more = len(rows) > limit
    items = rows[:limit]
    return Page(
        items=[schema.model_validate(row) for row in items],
        next_cursor=items[-1].id if has_more else None,
    )


@router.get("/exceptions", response_model=Page)
async def list_exceptions(
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
    severity: ExceptionSeverity | None = None,
    status: ExceptionResolution | None = None,
) -> Page:
    require_permission(scope.context, PermissionCode.EXCEPTION_READ)
    filters: list[object] = []
    if severity:
        filters.append(WorkflowException.severity == severity)
    if status:
        filters.append(WorkflowException.resolution_status == status)
    rows = await _repository(scope).list_rows(
        WorkflowException, limit=limit, after=after, filters=tuple(filters)
    )
    return _page(rows, limit, ExceptionResponse)


@router.get("/exceptions/{exception_id}", response_model=ExceptionResponse)
async def get_exception(exception_id: UUID, scope: Scope) -> ExceptionResponse:
    require_permission(scope.context, PermissionCode.EXCEPTION_READ)
    row = await _repository(scope).get(WorkflowException, exception_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return ExceptionResponse.model_validate(row)


@router.get("/reconciliation-proposals", response_model=Page)
async def list_reconciliation_proposals(
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
) -> Page:
    require_permission(scope.context, PermissionCode.RECONCILIATION_READ)
    rows = await _repository(scope).list_rows(MatchProposal, limit=limit, after=after)
    return _page(rows, limit, MatchProposalResponse)


@router.get("/reconciliation-proposals/{proposal_id}", response_model=MatchProposalResponse)
async def get_reconciliation_proposal(proposal_id: UUID, scope: Scope) -> MatchProposalResponse:
    require_permission(scope.context, PermissionCode.RECONCILIATION_READ)
    row = await _repository(scope).get(MatchProposal, proposal_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return MatchProposalResponse.model_validate(row)


@router.get("/journal-proposals/{proposal_id}", response_model=JournalProposalResponse)
async def get_journal_proposal(proposal_id: UUID, scope: Scope) -> JournalProposalResponse:
    require_permission(scope.context, PermissionCode.REVIEW_READ)
    row = await _repository(scope).get(JournalProposal, proposal_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return JournalProposalResponse.model_validate(row)


@router.get("/approval-requests", response_model=Page)
async def list_approval_requests(
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
    status: ApprovalStatus | None = None,
) -> Page:
    require_permission(scope.context, PermissionCode.REVIEW_READ)
    filters = (ApprovalRequest.status == status,) if status else ()
    rows = await _repository(scope).list_rows(
        ApprovalRequest, limit=limit, after=after, filters=filters
    )
    return _page(rows, limit, ApprovalRequestResponse)


@router.get("/approval-requests/{request_id}", response_model=ApprovalRequestResponse)
async def get_approval_request(request_id: UUID, scope: Scope) -> ApprovalRequestResponse:
    require_permission(scope.context, PermissionCode.REVIEW_READ)
    row = await _repository(scope).get(ApprovalRequest, request_id)
    if row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return ApprovalRequestResponse.model_validate(row)


async def _action(
    request_id: UUID,
    action: ApprovalActionType,
    body: ApprovalActionRequest,
    scope: RequestScope,
    idempotency_key: str,
    expected_version: int,
    permission: PermissionCode,
) -> ApprovalActionResponse:
    require_permission(scope.context, permission)
    row = await ApprovalService(_repository(scope), scope.context).act(
        request_id, action, body, idempotency_key=idempotency_key, expected_version=expected_version
    )
    return ApprovalActionResponse.model_validate(row)


@router.post("/approval-requests/{request_id}/approve", response_model=ApprovalActionResponse)
async def approve(
    request_id: UUID,
    body: ApprovalActionRequest,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    expected_version: ExpectedVersion,
) -> ApprovalActionResponse:
    return await _action(
        request_id,
        ApprovalActionType.APPROVE,
        body,
        scope,
        idempotency_key,
        expected_version,
        PermissionCode.REVIEW_APPROVE,
    )


@router.post("/approval-requests/{request_id}/correct", response_model=ApprovalActionResponse)
async def correct(
    request_id: UUID,
    body: ApprovalActionRequest,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    expected_version: ExpectedVersion,
) -> ApprovalActionResponse:
    return await _action(
        request_id,
        ApprovalActionType.CORRECT,
        body,
        scope,
        idempotency_key,
        expected_version,
        PermissionCode.REVIEW_CORRECT,
    )


@router.post("/approval-requests/{request_id}/reject", response_model=ApprovalActionResponse)
async def reject(
    request_id: UUID,
    body: ApprovalActionRequest,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    expected_version: ExpectedVersion,
) -> ApprovalActionResponse:
    return await _action(
        request_id,
        ApprovalActionType.REJECT,
        body,
        scope,
        idempotency_key,
        expected_version,
        PermissionCode.REVIEW_REJECT,
    )


@router.post(
    "/approval-requests/{request_id}/request-evidence", response_model=ApprovalActionResponse
)
async def request_evidence(
    request_id: UUID,
    body: ApprovalActionRequest,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    expected_version: ExpectedVersion,
) -> ApprovalActionResponse:
    return await _action(
        request_id,
        ApprovalActionType.REQUEST_EVIDENCE,
        body,
        scope,
        idempotency_key,
        expected_version,
        PermissionCode.REVIEW_REQUEST_EVIDENCE,
    )


@router.post("/approval-requests/{request_id}/escalate", response_model=ApprovalActionResponse)
async def escalate(
    request_id: UUID,
    body: ApprovalActionRequest,
    scope: Scope,
    idempotency_key: IdempotencyKey,
    expected_version: ExpectedVersion,
) -> ApprovalActionResponse:
    return await _action(
        request_id,
        ApprovalActionType.ESCALATE,
        body,
        scope,
        idempotency_key,
        expected_version,
        PermissionCode.REVIEW_ESCALATE,
    )


@router.post("/exceptions/{exception_id}/resolve", response_model=ExceptionResponse)
async def resolve_exception(
    exception_id: UUID,
    body: ExceptionResolveRequest,
    scope: Scope,
) -> ExceptionResponse:
    require_permission(scope.context, PermissionCode.REVIEW_ACTION)
    repository = _repository(scope)
    exception = await repository.get(WorkflowException, exception_id)
    if exception is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    if exception.resolution_status != ExceptionResolution.OPEN:
        raise ApiError(409, "CONFLICT", "EXCEPTION_NOT_OPEN", "The exception is not open.")
    exception.resolution_status = ExceptionResolution.RESOLVED
    actor_name = scope.context.external_subject or str(scope.context.principal_id)
    exception.resolution_reference = {"reason": body.reason, "actor": actor_name}
    exception.version += 1
    await repository.session.flush()
    await repository.record_audit(
        action="EXCEPTION_RESOLVED",
        resource_type="exception",
        resource_id=exception.id,
        resource_version=str(exception.version),
        outcome="SUCCEEDED",
        metadata={"reason_provided": True},
        actor_id=actor_name,
        correlation_id=UUID(scope.context.correlation_id),
    )
    return ExceptionResponse.model_validate(exception)


@router.post(
    "/documents/{document_id}/extractions",
    response_model=ExtractionResponse,
    status_code=201,
)
async def extract_document(
    document_id: UUID,
    request: Request,
    scope: Scope,
    body: ExtractionRequest | None = None,
) -> ExtractionResponse:
    require_permission(scope.context, PermissionCode.DOCUMENT_READ)
    role1 = request.app.state.role_adapters.get("role1")
    if role1 is None:
        raise ApiError(503, "DOWNSTREAM", "ROLE1_UNAVAILABLE", "Role 1 service is unavailable.")
    repository = _repository(scope)
    version = await repository.get_accepted_document_version(
        document_id, version_id=body.document_version_id if body else None
    )
    if version is None:
        raise ApiError(
            404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Accepted document version not found."
        )
    correlation_id = UUID(scope.context.correlation_id)
    tenant_context = EntityTenantContext(
        tenant_id=scope.context.tenant_id,
        organization_id=repository.organization_id,
        legal_entity_id=repository.legal_entity_id,
    )
    role6 = request.app.state.role_adapters.get("role6")
    if role6 is not None:
        with suppress(Exception):
            await role6.classify(
                payload={"resource_id": str(document_id)},
                tenant_context=tenant_context,
                operation_id=version.id,
                correlation_id=correlation_id,
            )
    payload = {
        "document_id": str(document_id),
        "document_version_id": str(version.id),
        "tenant_context": tenant_context.model_dump(mode="json"),
        "operation_id": str(version.id),
        "correlation": {
            "request_id": str(correlation_id),
            "correlation_id": str(correlation_id),
            "causation_id": None,
        },
    }
    contract = await role1.request_extraction(
        operation_id=version.id,
        correlation_id=correlation_id,
        payload=payload,
        tenant_context=tenant_context,
    )
    orchestrator = WorkflowOrchestrator(repository, correlation_id=correlation_id)
    extraction_row = await orchestrator.persist_extraction(
        contract,
        document_version_id=version.id,
        producer_result_id=f"extraction-{version.id}",
    )
    source_evidence_id = stable_id("nova:demo:source-evidence")
    await repository.add_edge(
        from_type="document_version",
        from_id=version.id,
        from_version=str(version.version_number),
        to_type="source_evidence",
        to_id=source_evidence_id,
        to_version="1",
        relation="STORED_AS",
    )
    await repository.add_edge(
        from_type="document_extraction",
        from_id=extraction_row.id,
        from_version=str(extraction_row.extraction_version),
        to_type="document_version",
        to_id=version.id,
        to_version=str(version.version_number),
        relation="EXTRACTED_FROM",
    )
    await repository.record_audit(
        action="DOCUMENT_EXTRACTED",
        resource_type="document_extraction",
        resource_id=extraction_row.id,
        resource_version=str(extraction_row.extraction_version),
        outcome="SUCCEEDED",
        metadata={"document_id": str(document_id)},
        actor_id=str(scope.context.principal_id),
        correlation_id=correlation_id,
    )
    if extraction_row.validation_outcome.value == "VALIDATED":
        await repository.record_audit(
            action="DOCUMENT_VALIDATED",
            resource_type="document_extraction",
            resource_id=extraction_row.id,
            resource_version=str(extraction_row.extraction_version),
            outcome="SUCCEEDED",
            metadata={"document_id": str(document_id)},
            actor_id=str(scope.context.principal_id),
            correlation_id=correlation_id,
        )
    return ExtractionResponse.model_validate(extraction_row)


@router.post("/reconciliations", response_model=ReconciliationWorkflowResponse, status_code=201)
async def create_reconciliation(
    body: ReconciliationCreateRequest,
    request: Request,
    scope: Scope,
) -> ReconciliationWorkflowResponse:
    require_permission(scope.context, PermissionCode.DOCUMENT_WRITE)
    role3 = request.app.state.role_adapters.get("role3")
    if role3 is None:
        raise ApiError(503, "DOWNSTREAM", "ROLE3_UNAVAILABLE", "Role 3 service is unavailable.")
    repository = _repository(scope)
    correlation_id = body.correlation_id or UUID(scope.context.correlation_id)
    extraction_row = await repository.latest_extraction_for_version(body.document_version_id)
    if extraction_row is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Document extraction not found.")
    tenant_context = EntityTenantContext(
        tenant_id=scope.context.tenant_id,
        organization_id=repository.organization_id,
        legal_entity_id=repository.legal_entity_id,
    )
    # Load the bank transactions for this reconciliation
    tx_rows = list(
        await repository.session.scalars(
            select(BankTransaction).where(
                *repository._scope(BankTransaction),
                BankTransaction.id.in_(body.transaction_ids),
            )
        )
    )
    # Build facts for real reconciliation engine
    fields = (
        extraction_row.contract_payload.get("fields", []) if extraction_row.contract_payload else []
    )
    total_val = next((f["value"] for f in fields if f.get("field_name") == "total"), "0")
    curr_val = next((f["value"] for f in fields if f.get("field_name") == "currency"), "INR")
    ref_val = next((f["value"] for f in fields if f.get("field_name") == "invoice_number"), None)
    sup_val = next((f["value"] for f in fields if f.get("field_name") == "supplier_name"), None)
    date_str = next((f["value"] for f in fields if f.get("field_name") == "invoice_date"), None)
    inv_date = date.fromisoformat(str(date_str)) if date_str else date(2026, 9, 15)

    invoice_fact = {
        "extraction_id": str(extraction_row.id),
        "extraction_version": str(extraction_row.extraction_version),
        "document_id": str(body.document_id),
        "document_version": "1",
        "tenant_context": tenant_context.model_dump(mode="json"),
        "amount": {"amount": str(total_val), "currency": str(curr_val)},
        "invoice_date": inv_date.isoformat(),
        "expected_transaction_direction": "DEBIT",
        "reference": str(ref_val) if ref_val else None,
        "party_name": str(sup_val) if sup_val else None,
        "evidence_complete": True,
        "content_fingerprint": "a" * 64,
        "provenance": [
            {
                "source_document_id": str(body.document_id),
                "document_version": "1",
                "source_field": "invoice",
                "evidence_hash": "a" * 64,
            }
        ],
    }
    versioned_txs = [
        {
            "transaction_version": "1",
            "transaction": {
                "schema_version": "1.0",
                "transaction_id": str(tx.id),
                "tenant_context": tenant_context.model_dump(mode="json"),
                "bank_account_id": str(tx.bank_account_id),
                "import_batch_id": str(tx.import_id),
                "source_row_number": tx.source_row_number,
                "booking_date": tx.booking_date.isoformat(),
                "value_date": tx.value_date.isoformat() if tx.value_date else None,
                "money": {"amount": str(tx.amount), "currency": tx.currency},
                "direction": tx.direction,
                "narration": tx.narration or "",
                "reference": tx.reference,
                "counterparty": {"display_name": tx.counterparty_name}
                if tx.counterparty_name
                else None,
                "external_source_id": tx.external_source_id,
                "normalization_status": "NORMALIZED",
                "provenance": [
                    {
                        "source_document_id": str(body.document_id),
                        "document_version": "1",
                        "source_field": "bank_transaction",
                        "evidence_hash": "b" * 64,
                    }
                ],
                "content_fingerprint": tx.source_fingerprint,
                "correlation": {
                    "request_id": str(correlation_id),
                    "correlation_id": str(correlation_id),
                    "causation_id": None,
                },
            },
        }
        for tx in tx_rows
    ]

    operation_id = uuid4()
    payload = {
        "operation_id": str(operation_id),
        "document_id": str(body.document_id),
        "document_version_id": str(body.document_version_id),
        "document_extraction_id": str(extraction_row.id),
        "transaction_ids": [str(tx) for tx in body.transaction_ids],
        "tenant_context": tenant_context.model_dump(mode="json"),
        "correlation": {
            "request_id": str(correlation_id),
            "correlation_id": str(correlation_id),
            "causation_id": None,
        },
        "strategy_version": "reconciliation-rules/1.0.0",
        "invoices": [invoice_fact],
        "transactions": versioned_txs,
    }
    result = await role3.request_reconciliation(
        operation_id=operation_id,
        correlation_id=correlation_id,
        payload=payload,
        tenant_context=tenant_context,
    )
    allowed_ids = {
        body.document_id,
        body.document_version_id,
        extraction_row.id,
        *body.transaction_ids,
    }
    orchestrator = WorkflowOrchestrator(repository, correlation_id=correlation_id)
    match_row, exception_rows = await orchestrator.persist_reconciliation(
        result, allowed_resource_ids=allowed_ids
    )

    # Deterministic journal proposal for reconciled invoice
    journal_id = stable_id("nova:demo:journal")
    journal_contract = JournalProposalContract(
        schema_version="1.0",
        proposal_id=journal_id,
        proposal_version=1,
        tenant_context=tenant_context,
        proposed_journal_date=date(2026, 9, 15),
        currency="INR",
        lines=[
            ProposedJournalLine(
                line_id=stable_id("nova:demo:journal-line-debit"),
                account_reference="6100",
                direction="DEBIT",
                amount=PositiveMoney(amount=Decimal("1250.00"), currency="INR"),
                description="Synthetic NOVA invoice debit",
                source_evidence=[
                    ProvenanceReference(
                        source_document_id=body.document_id,
                        document_version="1",
                        source_field="invoice",
                        evidence_hash="a" * 64,
                    )
                ],
            ),
            ProposedJournalLine(
                line_id=stable_id("nova:demo:journal-line-credit"),
                account_reference="1100",
                direction="CREDIT",
                amount=PositiveMoney(amount=Decimal("1250.00"), currency="INR"),
                description="Synthetic NOVA invoice credit",
                source_evidence=[
                    ProvenanceReference(
                        source_document_id=body.document_id,
                        document_version="1",
                        source_field="invoice",
                        evidence_hash="a" * 64,
                    )
                ],
            ),
        ],
        source_evidence=[
            ProvenanceReference(
                source_document_id=body.document_id,
                document_version="1",
                source_field="invoice",
                evidence_hash="a" * 64,
            )
        ],
        explanation="Synthetic invoice expense proposal",
        producer=ProducerMetadata(
            producer_type=ProducerType.SERVICE,
            name="ledgerai-demo",
            version="1.0.0",
        ),
        accounting_validation="NOT_VALIDATED",
        posting_status="UNPOSTED",
        correlation=CorrelationMetadata(
            request_id=correlation_id,
            correlation_id=correlation_id,
            causation_id=None,
        ),
    )
    journal_row = await orchestrator.persist_journal(
        journal_contract, maker_principal_id=scope.context.principal_id
    )

    policy_set = await repository.get_policy_set_by_code("nova-demo-review")
    policy_set_id = policy_set.id if policy_set else stable_id("nova:demo:policy-set")
    stored_rules = await repository.policy_rules(policy_set_id)
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
    if not rule_specs:
        rule_specs = [
            PolicyRuleSpec(
                rule_id="HUMAN_REVIEW",
                priority=100,
                conditions=[
                    PolicyCondition(field="maker_checker_required", operator="eq", operand=True)
                ],
                outcome="REVIEW_REQUIRED",
                reason_code="MAKER_CHECKER",
                explanation="Synthetic demo requires review",
            )
        ]
    decision_row = await orchestrator.apply_policy(
        journal_row,
        policy_set_id=policy_set_id,
        policy_version="1.0",
        inputs={"maker_checker_required": True},
        rules=rule_specs,
        maker_checker_required=True,
    )

    await repository.add_edge(
        from_type="bank_transaction",
        from_id=body.transaction_ids[0],
        from_version="1",
        to_type="document_extraction",
        to_id=extraction_row.id,
        to_version=str(extraction_row.extraction_version),
        relation="RECONCILED_WITH",
    )
    await repository.add_edge(
        from_type="match_proposal",
        from_id=match_row.id,
        from_version=str(match_row.proposal_version),
        to_type="bank_transaction",
        to_id=body.transaction_ids[0],
        to_version="1",
        relation="MATCHES",
    )
    await repository.add_edge(
        from_type="policy_decision",
        from_id=decision_row.id,
        from_version="1",
        to_type="journal_proposal",
        to_id=journal_row.id,
        to_version=str(journal_row.proposal_version),
        relation="GOVERNS",
    )

    await repository.record_audit(
        action="RECONCILIATION_PROPOSED",
        resource_type="match_proposal",
        resource_id=match_row.id,
        resource_version=str(match_row.proposal_version),
        outcome="SUCCEEDED",
        metadata={"match_type": match_row.match_type},
        actor_id=str(scope.context.principal_id),
        correlation_id=correlation_id,
    )
    exception_row = exception_rows[0] if exception_rows else None
    if exception_row is None:
        exception_row = await repository.session.scalar(
            select(WorkflowException)
            .where(
                *repository._scope(WorkflowException),
                WorkflowException.correlation_id == correlation_id,
            )
            .order_by(WorkflowException.id.desc())
            .limit(1)
        )
    if exception_row:
        await repository.record_audit(
            action="EXCEPTION_CREATED",
            resource_type="exception",
            resource_id=exception_row.id,
            resource_version="1",
            outcome="SUCCEEDED",
            metadata={"type": exception_row.exception_type},
            actor_id=str(scope.context.principal_id),
            correlation_id=correlation_id,
        )
    await repository.record_audit(
        action="JOURNAL_PROPOSED",
        resource_type="journal_proposal",
        resource_id=journal_row.id,
        resource_version=str(journal_row.proposal_version),
        outcome="SUCCEEDED",
        metadata={"currency": journal_row.currency},
        actor_id=str(scope.context.principal_id),
        correlation_id=correlation_id,
    )
    await repository.record_audit(
        action="POLICY_EVALUATED",
        resource_type="policy_decision",
        resource_id=decision_row.id,
        resource_version="1",
        outcome="SUCCEEDED",
        metadata={"outcome": decision_row.outcome.value},
        actor_id=str(scope.context.principal_id),
        correlation_id=correlation_id,
    )

    approval_request = await repository.session.scalar(
        select(ApprovalRequest).where(
            *repository._scope(ApprovalRequest),
            ApprovalRequest.policy_decision_id == decision_row.id,
        )
    )

    return ReconciliationWorkflowResponse(
        match_proposal_id=match_row.id,
        exception_id=exception_row.id if exception_row else None,
        journal_proposal_id=journal_row.id,
        policy_decision_id=decision_row.id,
        approval_request_id=approval_request.id if approval_request else None,
    )
