from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError
from test_contract_fixtures import FIXTURES, load

from ledgerai_contracts.v1.common import CorrelationMetadata, Money
from ledgerai_contracts.v1.documents import DocumentMetadata
from ledgerai_contracts.v1.events import EventEnvelope
from ledgerai_contracts.v1.jobs import ProcessingJob
from ledgerai_contracts.v1.tenancy import EntityTenantContext, TenantContext


def test_tenant_and_organization_cannot_be_omitted() -> None:
    with pytest.raises(ValidationError):
        TenantContext.model_validate({"legal_entity_id": "00000000-0000-4000-8000-000000000003"})


def test_entity_scoped_context_requires_legal_entity() -> None:
    with pytest.raises(ValidationError):
        EntityTenantContext.model_validate(
            {
                "tenant_id": "00000000-0000-4000-8000-000000000001",
                "organization_id": "00000000-0000-4000-8000-000000000002",
            }
        )


@pytest.mark.parametrize("bad", [1.25, 1, True])
def test_binary_float_and_numeric_money_inputs_are_rejected(bad: object) -> None:
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": bad, "currency": "INR"})


def test_decimal_string_preserves_exact_value_and_serialization() -> None:
    money = Money.model_validate({"amount": "1000000000000000000.00100", "currency": "INR"})
    assert money.amount == Decimal("1000000000000000000.00100")
    assert money.model_dump(mode="json")["amount"] == "1000000000000000000.00100"


@pytest.mark.parametrize("currency", ["inr", "IN", "INRR", "123"])
def test_invalid_currency_is_rejected(currency: str) -> None:
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": "1.00", "currency": currency})


@pytest.mark.parametrize("confidence", ["-0.01", "1.01"])
def test_invalid_confidence_is_rejected(confidence: str) -> None:
    from ledgerai_contracts.v1.documents import DocumentExtraction

    raw = load(FIXTURES / "document-extraction.valid-invoice.json")
    raw["fields"][0]["confidence"] = confidence
    with pytest.raises(ValidationError):
        DocumentExtraction.model_validate(raw)


def test_naive_timestamps_are_rejected_and_aware_are_normalized_to_utc() -> None:
    raw = load(FIXTURES / "document-metadata.valid.json")
    raw["uploaded_at"] = "2026-01-15T10:30:00"
    with pytest.raises(ValidationError):
        DocumentMetadata.model_validate(raw)
    raw["uploaded_at"] = "2026-01-15T10:30:00+05:30"
    parsed = DocumentMetadata.model_validate(raw)
    offset = parsed.uploaded_at.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0


def test_invalid_ids_are_rejected() -> None:
    with pytest.raises(ValidationError):
        CorrelationMetadata.model_validate(
            {"request_id": "not-a-uuid", "correlation_id": UUID(int=1)}
        )


def test_unknown_major_schema_version_is_rejected() -> None:
    raw = load(FIXTURES / "document-metadata.valid.json")
    raw["schema_version"] = "2.0"
    with pytest.raises(ValidationError):
        DocumentMetadata.model_validate(raw)


def test_illegal_job_state_is_rejected() -> None:
    raw = load(FIXTURES / "processing-job.queued.json")
    raw["state"] = "RUNNING"
    with pytest.raises(ValidationError):
        ProcessingJob.model_validate(raw)


def test_event_type_cannot_claim_an_incompatible_payload() -> None:
    raw = load(FIXTURES / "event.document.uploaded.v1.json")
    raw["event_type"] = "workflow.failed.v1"
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(raw)


def test_model_rejects_undocumented_fields() -> None:
    raw = load(FIXTURES / "document-metadata.valid.json")
    raw["trusted_client_tenant_override"] = True
    with pytest.raises(ValidationError):
        DocumentMetadata.model_validate(raw)
