# mypy: disable-error-code="no-untyped-def,no-untyped-call"

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ledgerai_backend.core.errors import ApiError
from ledgerai_backend.core.request_context import AuthorizationContext
from ledgerai_backend.integration.models import ApprovalActionType, ApprovalStatus
from ledgerai_backend.integration.schemas import ApprovalActionRequest
from ledgerai_backend.integration.service import ApprovalService


class Session:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, row: object) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None


def context(principal_id=None) -> AuthorizationContext:
    return AuthorizationContext(
        principal_id=principal_id or uuid4(),
        external_subject="reviewer",
        tenant_id=uuid4(),
        organization_id=uuid4(),
        legal_entity_id=uuid4(),
        membership_id=uuid4(),
        roles=frozenset({"reviewer"}),
        permissions=frozenset({"review:approve"}),
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
    )


def request(*, maker=None, version: int = 1, status=ApprovalStatus.OPEN, expired=False):
    return SimpleNamespace(
        id=uuid4(),
        version=version,
        status=status,
        subject_type="journal_proposal",
        subject_id=uuid4(),
        subject_version="3",
        policy_decision_id=uuid4(),
        maker_principal_id=maker,
        maker_checker_required=True,
        expires_at=datetime.now(UTC) + (-timedelta(seconds=1) if expired else timedelta(days=1)),
        terminal_action_id=None,
        updated_at=datetime.now(UTC),
    )


def repository(row):
    repo = SimpleNamespace(
        tenant_id=uuid4(),
        organization_id=uuid4(),
        legal_entity_id=uuid4(),
        session=Session(),
        existing_action=AsyncMock(return_value=None),
        lock_approval=AsyncMock(return_value=row),
        policy_decision=AsyncMock(),
        journal=AsyncMock(),
        has_blocking_exception=AsyncMock(return_value=False),
        add_outbox=lambda **_: None,
    )
    repo.expired = lambda value: value.expires_at <= datetime.now(UTC)
    repo.terminal = lambda value: value != ApprovalStatus.OPEN
    return repo


def body(*, version="3", reason=None, corrections=None) -> ApprovalActionRequest:
    return ApprovalActionRequest(
        reviewed_resource_version=version, reason=reason, structured_corrections=corrections
    )


async def act(service, row, action, payload, *, expected=1):
    return await service.act(
        row.id, action, payload, idempotency_key="approval-key-1", expected_version=expected
    )


@pytest.mark.asyncio
async def test_reject_is_immutable_terminal_action() -> None:
    row = request()
    repo = repository(row)
    result = await act(
        ApprovalService(repo, context()),
        row,
        ApprovalActionType.REJECT,
        body(reason="Invalid evidence"),
    )
    assert result.action == ApprovalActionType.REJECT
    assert row.status == ApprovalStatus.REJECTED
    assert row.version == 2
    assert row.terminal_action_id == result.id


@pytest.mark.asyncio
async def test_duplicate_action_returns_prior_result() -> None:
    row = request()
    repo = repository(row)
    prior = SimpleNamespace(approval_request_id=row.id, action=ApprovalActionType.REJECT)
    repo.existing_action.return_value = prior
    result = await act(
        ApprovalService(repo, context()), row, ApprovalActionType.REJECT, body(reason="same")
    )
    assert result is prior
    repo.lock_approval.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "payload", "code"),
    [
        (ApprovalActionType.REJECT, body(), "REASON_REQUIRED"),
        (ApprovalActionType.CORRECT, body(reason="fix"), "CORRECTIONS_REQUIRED"),
        (
            ApprovalActionType.APPROVE,
            body(corrections={"explanation": "x"}),
            "CORRECTIONS_NOT_ALLOWED",
        ),
        (ApprovalActionType.ESCALATE, body(), "REASON_REQUIRED"),
        (ApprovalActionType.REQUEST_EVIDENCE, body(), "REASON_REQUIRED"),
    ],
)
async def test_action_validation(action, payload, code) -> None:
    row = request()
    with pytest.raises(ApiError) as caught:
        await act(ApprovalService(repository(row), context()), row, action, payload)
    assert caught.value.code == code


@pytest.mark.asyncio
async def test_stale_request_version_is_rejected() -> None:
    row = request(version=2)
    with pytest.raises(ApiError) as caught:
        await act(
            ApprovalService(repository(row), context()),
            row,
            ApprovalActionType.REJECT,
            body(reason="x"),
        )
    assert caught.value.code == "STALE_APPROVAL"


@pytest.mark.asyncio
async def test_stale_subject_version_is_rejected() -> None:
    row = request()
    with pytest.raises(ApiError) as caught:
        await act(
            ApprovalService(repository(row), context()),
            row,
            ApprovalActionType.REJECT,
            body(version="2", reason="x"),
        )
    assert caught.value.code == "STALE_RESOURCE_VERSION"


@pytest.mark.asyncio
async def test_expired_request_is_rejected_and_marked() -> None:
    row = request(expired=True)
    with pytest.raises(ApiError) as caught:
        await act(
            ApprovalService(repository(row), context()),
            row,
            ApprovalActionType.REJECT,
            body(reason="x"),
        )
    assert caught.value.code == "APPROVAL_EXPIRED"
    assert row.status == ApprovalStatus.EXPIRED


@pytest.mark.asyncio
async def test_terminal_request_cannot_be_replayed() -> None:
    row = request(status=ApprovalStatus.REJECTED)
    with pytest.raises(ApiError) as caught:
        await act(
            ApprovalService(repository(row), context()),
            row,
            ApprovalActionType.REJECT,
            body(reason="x"),
        )
    assert caught.value.code == "APPROVAL_ALREADY_DECIDED"


@pytest.mark.asyncio
async def test_maker_cannot_self_approve() -> None:
    actor = uuid4()
    row = request(maker=actor)
    with pytest.raises(ApiError) as caught:
        await act(
            ApprovalService(repository(row), context(actor)),
            row,
            ApprovalActionType.APPROVE,
            body(),
        )
    assert caught.value.code == "MAKER_CHECKER_VIOLATION"


def test_mass_assignment_in_corrections_is_rejected() -> None:
    with pytest.raises(ValueError):
        body(reason="attack", corrections={"posting_status": "POSTED"})
