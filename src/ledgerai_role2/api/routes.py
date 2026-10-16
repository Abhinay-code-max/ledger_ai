"""FastAPI route handlers for Role 2 deterministic financial core."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ledgerai_contracts.v1.accounting import (
    AccountingValidationResult,
    FinancialStatementSnapshot,
    JournalPostingResult,
    PeriodCloseResult,
    PeriodCloseValidationResult,
    PostingStatusResult,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role2.domain.models import Account, AccountType, NormalBalance, PeriodStatus
from ledgerai_role2.domain.state_machine import IdempotencyConflictError
from ledgerai_role2.security.token import (
    ServiceAuthenticationError,
    ServiceAuthorizationError,
    verify_service_token,
)
from ledgerai_role2.service import Role2Service

router = APIRouter()


class AccountingAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(pattern=r"^1\.0$")
    tenant_context: EntityTenantContext
    operation_id: UUID
    proposal_id: UUID
    proposal_version: str
    accepted: bool
    validation_reference: str | None = Field(default=None, max_length=200)


class AccountCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_code: str = Field(min_length=1, max_length=160)
    account_name: str = Field(min_length=1, max_length=300)
    account_type: AccountType
    currency: str = Field(pattern=r"^[A-Z]{3}$", default="INR")
    normal_balance: NormalBalance | None = None
    is_active: bool = True
    description: str | None = None


class PeriodCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period_id: UUID
    period_start: date
    period_end: date
    state: PeriodStatus = PeriodStatus.OPEN


class ReversalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reversal_date: date
    accounting_period_id: UUID
    reason: str = Field(min_length=1, max_length=500)


def _authenticate_request(
    request: Request,
    authorization: str | None,
    x_tenant_id: UUID | None,
    x_operation_id: UUID | None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify service token and ensure tenant/operation binding."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "SERVICE_AUTHENTICATION_FAILED", "message": "Missing bearer token."},
        )
    raw_token = authorization.split("Bearer ", 1)[1].strip()
    settings = request.app.state.settings

    try:
        claims = verify_service_token(
            raw_token,
            secret=settings.service_token_secret.get_secret_value(),
            expected_audience=settings.service_token_audience,
            expected_issuer=settings.service_token_issuer,
            expected_tenant_id=x_tenant_id,
            expected_operation_id=x_operation_id,
            clock_skew_seconds=settings.allowed_clock_skew_seconds,
        )
        if payload is not None:
            p_op = payload.get("operation_id")
            if p_op and str(p_op) != str(claims.get("operation_id")):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "OPERATION_BINDING_MISMATCH",
                        "message": "Operation binding mismatch.",
                    },
                )
            p_tc = payload.get("tenant_context")
            if isinstance(p_tc, dict):
                p_tid = p_tc.get("tenant_id")
                if p_tid and str(p_tid) != str(claims.get("tenant_id")):
                    raise HTTPException(
                        status_code=403,
                        detail={"code": "TENANT_MISMATCH", "message": "Tenant mismatch."},
                    )
        return claims
    except HTTPException:
        raise
    except ServiceAuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ServiceAuthorizationError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


def _get_service(
    request: Request,
    tenant_id: UUID,
    organization_id: UUID,
    legal_entity_id: UUID,
) -> Role2Service:
    context = EntityTenantContext(
        tenant_id=tenant_id,
        organization_id=organization_id,
        legal_entity_id=legal_entity_id,
    )
    repo = request.app.state.get_repository(context)
    return Role2Service(repo, service_version=request.app.state.settings.service_version)


@router.post("/v1/journal-posting-requests", response_model=AccountingAcceptance)
async def request_posting_validation(
    payload: dict[str, Any],
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> AccountingAcceptance:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id, payload=payload)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)

    proposal_id = UUID(str(payload.get("proposal_id", x_operation_id)))
    proposal_version = int(str(payload.get("proposal_version", "1")))
    proposed_date = date.fromisoformat(str(payload.get("proposed_journal_date", date.today())))
    currency = str(payload.get("currency", "INR"))
    explanation = str(payload.get("explanation", "Journal proposal"))
    lines_payload = list(payload.get("lines", []))
    source_evidence = list(payload.get("source_evidence", []))
    approval_decision = payload.get("approval_decision")

    result = await service.accept_posting_request(
        operation_id=x_operation_id,
        proposal_id=proposal_id,
        proposal_version=proposal_version,
        proposed_journal_date=proposed_date,
        currency=currency,
        explanation=explanation,
        lines_payload=lines_payload,
        source_evidence=source_evidence,
        approval_decision=approval_decision,
    )
    return AccountingAcceptance.model_validate(result)


@router.post("/v1/accounting-validations", response_model=AccountingValidationResult)
async def validate_posting(
    payload: dict[str, Any],
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> AccountingValidationResult:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id, payload=payload)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)

    proposal_raw = payload.get("proposal")
    proposal_id = (
        UUID(str(proposal_raw.get("resource_id")))
        if isinstance(proposal_raw, dict)
        else UUID(str(payload.get("proposal_id", x_operation_id)))
    )
    proposal_version = int(str(payload.get("proposal_version", "1")))
    period_id = (
        UUID(str(payload["accounting_period_id"]))
        if "accounting_period_id" in payload
        else proposal_id
    )

    try:
        return await service.validate_posting(
            operation_id=x_operation_id,
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            accounting_period_id=period_id,
            raw_payload=payload,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(exc)},
        ) from exc


@router.post("/v1/journal-postings", response_model=JournalPostingResult)
async def post_journal(
    payload: dict[str, Any],
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> JournalPostingResult:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id, payload=payload)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)

    proposal_raw = payload.get("proposal")
    proposal_id = (
        UUID(str(proposal_raw.get("resource_id")))
        if isinstance(proposal_raw, dict)
        else UUID(str(payload.get("proposal_id", x_operation_id)))
    )
    proposal_version = int(str(payload.get("proposal_version", "1")))
    period_id = (
        UUID(str(payload["accounting_period_id"]))
        if "accounting_period_id" in payload
        else proposal_id
    )

    import os

    if os.environ.get("LEDGERAI_DEMO_UNKNOWN_POSTING", "false").lower() == "true" and not getattr(
        request.app.state, "_simulated_unknown_posting", False
    ):
        request.app.state._simulated_unknown_posting = True
        raise HTTPException(504, "synthetic unknown outcome")

    try:
        return await service.post_journal(
            operation_id=x_operation_id,
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            accounting_period_id=period_id,
            raw_payload=payload,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(exc)},
        ) from exc


@router.post("/v1/journal-posting-status", response_model=PostingStatusResult)
async def get_posting_status(
    payload: dict[str, Any],
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> PostingStatusResult:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id, payload=payload)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)
    target_op_id = UUID(str(payload.get("operation_id", x_operation_id)))
    return await service.get_posting_status(operation_id=target_op_id)


@router.post("/v1/period-close-validations", response_model=PeriodCloseValidationResult)
async def validate_period_close(
    payload: dict[str, Any],
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> PeriodCloseValidationResult:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id, payload=payload)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)
    period_id = UUID(str(payload["accounting_period_id"]))
    return await service.validate_period_close(
        operation_id=x_operation_id,
        accounting_period_id=period_id,
    )


@router.post("/v1/period-closes", response_model=PeriodCloseResult)
async def close_period(
    payload: dict[str, Any],
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> PeriodCloseResult:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id, payload=payload)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)
    period_id = UUID(str(payload["accounting_period_id"]))
    try:
        return await service.close_period(
            operation_id=x_operation_id,
            accounting_period_id=period_id,
            raw_payload=payload,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(exc)},
        ) from exc


@router.post("/v1/period-close-status", response_model=PeriodCloseResult)
async def get_period_close_status(
    payload: dict[str, Any],
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> PeriodCloseResult:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id, payload=payload)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)
    target_op_id = UUID(str(payload.get("operation_id", x_operation_id)))
    return await service.get_period_close_status(operation_id=target_op_id)


@router.post("/v1/financial-statements", response_model=FinancialStatementSnapshot)
async def get_financial_statement(
    payload: dict[str, Any],
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> FinancialStatementSnapshot:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id, payload=payload)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)
    period_id = UUID(str(payload["accounting_period_id"]))
    statement_type = str(payload["statement_type"])
    if "as_of" in payload:
        raw_as_of = str(payload["as_of"])
        parsed_as_of = datetime.fromisoformat(
            raw_as_of.replace("Z", "+00:00") if raw_as_of.endswith("Z") else raw_as_of
        )
        as_of = (
            parsed_as_of.replace(tzinfo=UTC)
            if parsed_as_of.tzinfo is None
            else parsed_as_of.astimezone(UTC)
        )
    else:
        as_of = datetime.now(UTC)
    currency = str(payload.get("currency", "INR"))
    include_summary = bool(payload.get("include_summary", False))
    return await service.generate_statement(
        operation_id=x_operation_id,
        accounting_period_id=period_id,
        statement_type=statement_type,
        as_of=as_of,
        currency=currency,
        include_summary=include_summary,
    )


@router.post("/v1/journals/{journal_id}/reversals", response_model=JournalPostingResult)
async def reverse_journal(
    journal_id: UUID,
    payload: ReversalPayload,
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> JournalPostingResult:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)
    return await service.reverse_posted_journal(
        operation_id=x_operation_id,
        journal_id=journal_id,
        accounting_period_id=payload.accounting_period_id,
        reversal_date=payload.reversal_date,
        reason=payload.reason,
    )


# -------------------------------------------------------------
# Auxiliary Management / Seed Endpoints
# -------------------------------------------------------------
@router.post("/v1/accounts")
async def create_account(
    payload: AccountCreatePayload,
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)
    account = Account.create(
        code=payload.account_code,
        name=payload.account_name,
        account_type=payload.account_type,
        currency=payload.currency,
        normal_balance=payload.normal_balance,
        is_active=payload.is_active,
        description=payload.description,
    )
    saved = await service.repo.save_account(account)
    return {
        "account_code": saved.account_code,
        "account_name": saved.account_name,
        "account_type": saved.account_type,
        "normal_balance": saved.normal_balance,
        "currency": saved.currency,
        "is_active": saved.is_active,
    }


@router.post("/v1/periods")
async def create_period(
    payload: PeriodCreatePayload,
    request: Request,
    x_tenant_id: Annotated[UUID, Header()],
    x_organization_id: Annotated[UUID, Header()],
    x_legal_entity_id: Annotated[UUID, Header()],
    x_operation_id: Annotated[UUID, Header()],
    x_correlation_id: Annotated[UUID, Header()],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _authenticate_request(request, authorization, x_tenant_id, x_operation_id)
    service = _get_service(request, x_tenant_id, x_organization_id, x_legal_entity_id)
    saved = await service.repo.save_period(
        period_id=payload.period_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        state=payload.state,
    )
    return {
        "period_id": str(saved.id),
        "period_start": saved.period_start.isoformat(),
        "period_end": saved.period_end.isoformat(),
        "state": saved.state,
    }


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "role2-financial-core", "version": "1.0.0"}


@router.get("/health/ready")
@router.get("/health/live")
async def health_ready() -> dict[str, str]:
    return {"status": "ready"}
