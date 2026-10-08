from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ledgerai_backend.assurance.models import (
    AuditEvent as AuditEventRow,
)
from ledgerai_backend.assurance.models import (
    PostingOperation,
)
from ledgerai_backend.assurance.models import (
    ProgressProjection as ProgressProjectionRow,
)
from ledgerai_backend.assurance.schemas import (
    AuditEventResponse,
    PostingOperationResponse,
    ProgressProjectionResponse,
)
from ledgerai_contracts.v1.accounting import JournalPostingResult, PeriodCloseResult


def posting_result(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "1.0",
        "tenant_context": {
            "tenant_id": str(uuid4()),
            "organization_id": str(uuid4()),
            "legal_entity_id": str(uuid4()),
        },
        "operation_id": str(uuid4()),
        "proposal_id": str(uuid4()),
        "proposal_version": 1,
        "outcome": "POSTED",
        "posted_journal_id": str(uuid4()),
        "posted_at": datetime.now(UTC).isoformat(),
        "ledger_references": [{"resource_type": "posted_journal", "resource_id": str(uuid4())}],
        "issues": [],
        "producer": {"producer_type": "SERVICE", "name": "role2", "version": "2.0"},
        "correlation": {
            "request_id": str(uuid4()),
            "correlation_id": str(uuid4()),
            "causation_id": None,
        },
    }
    value.update(updates)
    return value


@pytest.mark.parametrize(
    "updates",
    [
        {"posted_journal_id": None},
        {"posted_at": None},
        {"ledger_references": []},
        {"outcome": "FAILED"},
    ],
)
def test_posting_confirmation_contract_is_atomic(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        JournalPostingResult.model_validate(posting_result(**updates))


def test_closed_period_requires_closed_timestamp() -> None:
    raw = posting_result()
    raw.pop("proposal_id")
    raw.pop("proposal_version")
    raw.pop("posted_journal_id")
    raw.pop("posted_at")
    raw.pop("ledger_references")
    raw["accounting_period_id"] = str(uuid4())
    raw["outcome"] = "CLOSED"
    raw["closed_at"] = None
    with pytest.raises(ValidationError):
        PeriodCloseResult.model_validate(raw)


@pytest.mark.parametrize(
    ("table", "schema", "excluded"),
    [
        (PostingOperation, PostingOperationResponse, {"confirmation"}),
        (AuditEventRow, AuditEventResponse, {"metadata"}),
        (ProgressProjectionRow, ProgressProjectionResponse, set()),
    ],
)
def test_response_models_have_orm_column_parity(
    table: type[object], schema: type[object], excluded: set[str]
) -> None:
    columns = set(table.__table__.columns.keys())  # type: ignore[attr-defined]
    fields = set(schema.model_fields) - excluded  # type: ignore[attr-defined]
    aliases = {
        field.validation_alias
        for field in schema.model_fields.values()  # type: ignore[attr-defined]
        if isinstance(field.validation_alias, str)
    }
    assert fields - {"metadata"} <= columns
    assert aliases <= set(table.__mapper__.attrs.keys())  # type: ignore[attr-defined]


def test_audit_metadata_uses_non_reserved_orm_attribute() -> None:
    event_id = uuid4()
    row = AuditEventRow(
        tenant_id=uuid4(),
        organization_id=uuid4(),
        legal_entity_id=uuid4(),
        audit_event_id=event_id,
        actor_type="SERVICE",
        actor_id="ledgerai-backend",
        action="TESTED",
        resource_type="test",
        resource_id=uuid4(),
        outcome="SUCCEEDED",
        correlation_id=uuid4(),
        audit_metadata={"safe": True},
        event_hash="a" * 64,
        occurred_at=datetime.now(UTC),
    )
    response = AuditEventResponse.model_validate(row)
    assert response.audit_event_id == event_id
    assert response.metadata == {"safe": True}
