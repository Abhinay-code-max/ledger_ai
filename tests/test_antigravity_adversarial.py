"""Independent adversarial validation tests added by Antigravity.

These tests independently verify Phase 0 contract behavior against adversarial
inputs, boundary conditions, schema parity, and edge cases.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import jsonschema  # type: ignore[import-untyped]
import pytest
from pydantic import ValidationError

from ledgerai_contracts.v1 import (
    ApprovalDecision,
    DocumentMetadata,
    EntityTenantContext,
    EventEnvelope,
    JournalProposal,
    Money,
    ProcessingJob,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "shared" / "fixtures" / "contracts" / "v1"
SCHEMAS = ROOT / "shared" / "schemas" / "v1"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def load_schema(name: str) -> dict[str, object]:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))  # type: ignore[no-any-return]


# ------------------------------------------------------------------------------
# 1. Money Adversarial Tests
# ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_amount",
    [
        "1e5",
        "1E5",
        " 1250.00",
        "1250.00 ",
        "NaN",
        "Infinity",
        "-Infinity",
        "",
        "1,000.50",
        "12.34.56",
        "--10.00",
    ],
)
def test_adversarial_money_amounts_rejected(bad_amount: str) -> None:
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": bad_amount, "currency": "USD"})


def test_money_negative_amount_acceptance_behavior() -> None:
    """Documents that Money accepts negative amounts, creating potential ambiguity.

    When combined with BankTransaction or ProposedJournalLine which already have
    explicit direction ('DEBIT' / 'CREDIT'), negative amounts can create
    double-negative interpretations.
    """
    negative_money = Money.model_validate({"amount": "-150.25", "currency": "USD"})
    assert negative_money.amount == Decimal("-150.25")
    assert negative_money.model_dump(mode="json")["amount"] == "-150.25"


def test_money_exact_decimal_preservation_and_large_values() -> None:
    large = "9999999999999999999999999999999999999999.99"
    m = Money.model_validate({"amount": large, "currency": "INR"})
    assert str(m.amount) == large
    assert m.model_dump(mode="json")["amount"] == large


# ------------------------------------------------------------------------------
# 2. Tenant Context Adversarial Tests
# ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        "not-a-uuid",
        "00000000-0000-0000-0000-00000000000g",
        12345,
    ],
)
def test_tenant_context_malformed_ids_rejected(bad_id: object) -> None:
    with pytest.raises(ValidationError):
        EntityTenantContext.model_validate(
            {
                "tenant_id": bad_id,
                "organization_id": uuid4(),
                "legal_entity_id": uuid4(),
            }
        )


def test_tenant_context_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        EntityTenantContext.model_validate(
            {
                "tenant_id": uuid4(),
                "organization_id": uuid4(),
                "legal_entity_id": uuid4(),
                "injected_tenant_override": str(uuid4()),
            }
        )


def test_event_envelope_rejects_payload_tenant_mismatch() -> None:
    """Envelope and nested business-object tenant contexts cannot diverge."""
    raw = load_fixture("event.document.uploaded.v1.json")
    # Mutate the payload's tenant_id to a different tenant
    foreign_tenant = "ffffffff-ffff-4000-8000-000000000001"
    raw_payload = raw["payload"]
    assert isinstance(raw_payload, dict)
    doc = raw_payload["document"]
    assert isinstance(doc, dict)
    doc_tenant = doc["tenant_context"]
    assert isinstance(doc_tenant, dict)
    doc_tenant["tenant_id"] = foreign_tenant

    with pytest.raises(ValidationError, match="tenant context must match"):
        EventEnvelope.model_validate(raw)


# ------------------------------------------------------------------------------
# 3. Journal Proposal & Approval Safety Tests
# ------------------------------------------------------------------------------


def test_journal_proposal_cannot_be_posted() -> None:
    raw = load_fixture("journal-proposal.unposted.json")
    raw["posting_status"] = "POSTED"
    with pytest.raises(ValidationError):
        JournalProposal.model_validate(raw)


def test_journal_proposal_rejects_valid_accounting_claim() -> None:
    """Role 4 proposals cannot self-assert Role 2 deterministic validation."""
    raw = load_fixture("journal-proposal.unposted.json")
    raw["accounting_validation"] = "VALID"
    with pytest.raises(ValidationError):
        JournalProposal.model_validate(raw)


def test_approval_decision_rejects_none_resource_version() -> None:
    """Every approval action binds to an exact immutable resource version."""
    raw = load_fixture("approval-decision.approved.json")
    reviewed = raw["reviewed_resource"]
    assert isinstance(reviewed, dict)
    reviewed["resource_version"] = None

    with pytest.raises(ValidationError):
        ApprovalDecision.model_validate(raw)


def test_approval_decision_correct_requires_structured_corrections() -> None:
    raw = load_fixture("approval-decision.approved.json")
    raw["action"] = "CORRECT"
    raw["structured_corrections"] = None
    with pytest.raises(ValidationError, match="requires structured_corrections"):
        ApprovalDecision.model_validate(raw)


# ------------------------------------------------------------------------------
# 4. Processing Job Invariants
# ------------------------------------------------------------------------------


def test_processing_job_completed_requires_completed_at() -> None:
    raw = load_fixture("processing-job.processing.json")
    raw["state"] = "COMPLETED"
    raw["completed_at"] = None
    with pytest.raises(ValidationError, match="COMPLETED requires completed_at"):
        ProcessingJob.model_validate(raw)


def test_processing_job_retry_scheduled_requires_retry_at() -> None:
    raw = load_fixture("processing-job.processing.json")
    raw["state"] = "RETRY_SCHEDULED"
    raw["retry_at"] = None
    with pytest.raises(ValidationError, match="RETRY_SCHEDULED requires retry_at"):
        ProcessingJob.model_validate(raw)


def test_processing_job_failed_requires_error_code() -> None:
    raw = load_fixture("processing-job.processing.json")
    raw["state"] = "FAILED"
    raw["error_code"] = None
    with pytest.raises(ValidationError, match="failed states require error_code"):
        ProcessingJob.model_validate(raw)


def test_processing_job_attempt_cannot_exceed_max_attempts() -> None:
    raw = load_fixture("processing-job.processing.json")
    raw["attempt_number"] = 4
    raw["maximum_attempts"] = 3
    with pytest.raises(ValidationError, match="attempt_number cannot exceed maximum_attempts"):
        ProcessingJob.model_validate(raw)


# ------------------------------------------------------------------------------
# 5. Schema vs Model Parity Discrepancies
# ------------------------------------------------------------------------------


def test_event_envelope_json_schema_binds_type_to_payload() -> None:
    """Python and Draft 2020-12 schema both reject a mismatched event payload."""
    ee_schema = load_schema("event-envelope.schema.json")
    event_data = load_fixture("event.document.uploaded.v1.json")
    # Change event_type to an incompatible type
    event_data["event_type"] = "workflow.failed.v1"

    # Python rejects this
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(event_data)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(ee_schema).validate(event_data)


def test_schema_version_is_required_in_model_and_schema() -> None:
    """External payloads must explicitly declare their supported contract version."""
    doc_schema = load_schema("document-metadata.schema.json")
    required = doc_schema.get("required")
    assert isinstance(required, list)
    assert "schema_version" in required

    raw = load_fixture("document-metadata.valid.json")
    del raw["schema_version"]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(doc_schema).validate(raw)
    with pytest.raises(ValidationError):
        DocumentMetadata.model_validate(raw)
