from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import jsonschema  # type: ignore[import-untyped]
import pytest
from pydantic import BaseModel, ValidationError

from ledgerai_contracts.v1.approvals import ApprovalDecision
from ledgerai_contracts.v1.audit import AuditEvent
from ledgerai_contracts.v1.documents import DocumentExtraction, DocumentMetadata
from ledgerai_contracts.v1.errors import ErrorEnvelope
from ledgerai_contracts.v1.events import EVENT_REGISTRY, EventEnvelope
from ledgerai_contracts.v1.exceptions import ExceptionRecord
from ledgerai_contracts.v1.jobs import ProcessingJob
from ledgerai_contracts.v1.journals import JournalProposal
from ledgerai_contracts.v1.policy import PolicyDecision
from ledgerai_contracts.v1.reconciliation import MatchProposal
from ledgerai_contracts.v1.transactions import BankTransaction

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "shared" / "fixtures" / "contracts" / "v1"
SCHEMAS = ROOT / "shared" / "schemas" / "v1"


def load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def schema_validator(name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(load(SCHEMAS / f"{name}.schema.json"))


def assert_model_and_schema_reject(
    model: type[BaseModel], schema_name: str, raw: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(raw)
    with pytest.raises(jsonschema.ValidationError):
        schema_validator(schema_name).validate(raw)


EVENT_FIXTURES = {
    event_type: FIXTURES / f"event.{event_type}.json" for event_type in EVENT_REGISTRY
}


@pytest.mark.parametrize("event_type", EVENT_REGISTRY)
def test_each_registered_event_matches_model_and_schema(event_type: str) -> None:
    raw = load(EVENT_FIXTURES[event_type])
    parsed = EventEnvelope.model_validate(raw)
    schema_validator("event-envelope").validate(raw)
    assert parsed.event_type == event_type
    assert len(EVENT_REGISTRY) == 17


@pytest.mark.parametrize("event_type", EVENT_REGISTRY)
def test_every_event_rejects_a_payload_from_an_incompatible_variant(event_type: str) -> None:
    raw = load(EVENT_FIXTURES[event_type])
    expected_model = EVENT_REGISTRY[event_type].payload_model
    other_type = next(
        candidate
        for candidate, spec in EVENT_REGISTRY.items()
        if spec.payload_model is not expected_model
    )
    raw["payload"] = load(EVENT_FIXTURES[other_type])["payload"]
    assert_model_and_schema_reject(EventEnvelope, "event-envelope", raw)


def test_unknown_event_type_and_arbitrary_payload_are_rejected() -> None:
    raw = load(EVENT_FIXTURES["document.uploaded.v1"])
    raw["event_type"] = "unknown.event.v1"
    assert_model_and_schema_reject(EventEnvelope, "event-envelope", raw)

    raw = load(EVENT_FIXTURES["document.uploaded.v1"])
    raw["payload"] = {"arbitrary": "dictionary"}
    assert_model_and_schema_reject(EventEnvelope, "event-envelope", raw)


@pytest.mark.parametrize("event_type", EVENT_REGISTRY)
def test_event_payloads_forbid_undocumented_properties(event_type: str) -> None:
    raw = load(EVENT_FIXTURES[event_type])
    raw["payload"]["undocumented"] = True
    assert_model_and_schema_reject(EventEnvelope, "event-envelope", raw)


TENANT_PAYLOAD_PATHS = {
    "document.uploaded.v1": ("document",),
    "document.extracted.v1": ("extraction",),
    "reconciliation.proposed.v1": ("proposal",),
    "exception.created.v1": ("exception",),
    "journal.proposal.created.v1": ("proposal",),
    "policy.evaluated.v1": ("decision",),
    "approval.decided.v1": ("decision",),
}


@pytest.mark.parametrize("event_type,path", TENANT_PAYLOAD_PATHS.items())
@pytest.mark.parametrize("tenant_key", ["tenant_id", "organization_id", "legal_entity_id"])
def test_nested_event_tenant_components_must_match(
    event_type: str, path: tuple[str, ...], tenant_key: str
) -> None:
    raw = load(EVENT_FIXTURES[event_type])
    nested = raw["payload"]
    for segment in path:
        nested = nested[segment]
    nested["tenant_context"][tenant_key] = str(uuid4())
    with pytest.raises(ValidationError, match="tenant context must match"):
        EventEnvelope.model_validate(raw)


def test_event_schema_documents_unrepresentable_tenant_equality_rule() -> None:
    schema = load(SCHEMAS / "event-envelope.schema.json")
    extension = schema["x-ledgerai-tenant-context-invariant"]
    assert extension["organization_scoped_events"] == []
    assert set(extension["event_rules"]) == set(EVENT_REGISTRY)
    assert "cannot compare UUID values" in extension["enforcement"]

    # Draft 2020-12 has no standard cross-path value equality keyword; Pydantic is authoritative.
    raw = load(EVENT_FIXTURES["document.uploaded.v1"])
    raw["payload"]["document"]["tenant_context"]["tenant_id"] = str(uuid4())
    schema_validator("event-envelope").validate(raw)
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(raw)


TOP_LEVEL_CONTRACTS: list[tuple[type[BaseModel], str, str]] = [
    (ApprovalDecision, "approval-decision", "approval-decision.approved.json"),
    (AuditEvent, "audit-event", "audit-event.approval.json"),
    (BankTransaction, "bank-transaction", "bank-transaction.normalized.json"),
    (DocumentExtraction, "document-extraction", "document-extraction.valid-invoice.json"),
    (DocumentMetadata, "document-metadata", "document-metadata.valid.json"),
    (ErrorEnvelope, "error-envelope", "error.internal.json"),
    (EventEnvelope, "event-envelope", "event.document.uploaded.v1.json"),
    (ExceptionRecord, "exception", "exception.amount-mismatch.json"),
    (JournalProposal, "journal-proposal", "journal-proposal.unposted.json"),
    (MatchProposal, "match-proposal", "match-proposal.high-confidence.json"),
    (PolicyDecision, "policy-decision", "policy-decision.review-required.json"),
    (ProcessingJob, "processing-job", "processing-job.queued.json"),
]


@pytest.mark.parametrize("model,schema_name,fixture", TOP_LEVEL_CONTRACTS)
def test_schema_version_is_explicit_and_required_everywhere(
    model: type[BaseModel], schema_name: str, fixture: str
) -> None:
    raw = load(FIXTURES / fixture)
    model.model_validate(raw)
    schema_validator(schema_name).validate(raw)
    assert "schema_version" in load(SCHEMAS / f"{schema_name}.schema.json")["required"]

    missing = copy.deepcopy(raw)
    del missing["schema_version"]
    assert_model_and_schema_reject(model, schema_name, missing)
    for bad_version in ("v1", "1", "2.0", "1.1", None):
        invalid = copy.deepcopy(raw)
        invalid["schema_version"] = bad_version
        assert_model_and_schema_reject(model, schema_name, invalid)


@pytest.mark.parametrize("action", ["APPROVE", "CORRECT", "REJECT", "REQUEST_EVIDENCE", "ESCALATE"])
def test_every_approval_action_requires_exact_version(action: str) -> None:
    raw = load(FIXTURES / "approval-decision.approved.json")
    raw["action"] = action
    raw["structured_corrections"] = {"proposal_version": 2} if action == "CORRECT" else None
    ApprovalDecision.model_validate(raw)
    schema_validator("approval-decision").validate(raw)
    for bad_version in (None, "", " ", "bad version", ".1", "1."):
        invalid = copy.deepcopy(raw)
        invalid["reviewed_resource"]["resource_version"] = bad_version
        assert_model_and_schema_reject(ApprovalDecision, "approval-decision", invalid)
    missing = copy.deepcopy(raw)
    del missing["reviewed_resource"]["resource_version"]
    assert_model_and_schema_reject(ApprovalDecision, "approval-decision", missing)


def test_approval_serializes_and_preserves_a_different_exact_version() -> None:
    raw = load(FIXTURES / "approval-decision.rejected.json")
    raw["reviewed_resource"]["resource_version"] = "proposal-v2"
    decision = ApprovalDecision.model_validate(raw)
    assert decision.reviewed_resource.resource_version == "proposal-v2"
    assert (
        decision.model_dump(mode="json")["reviewed_resource"]["resource_version"] == "proposal-v2"
    )


@pytest.mark.parametrize("claim", ["VALID", "INVALID", "PASSED", "APPROVED", "POSTED", "custom"])
def test_journal_proposal_rejects_self_asserted_validation(claim: str) -> None:
    raw = load(FIXTURES / "journal-proposal.unposted.json")
    raw["accounting_validation"] = claim
    assert_model_and_schema_reject(JournalProposal, "journal-proposal", raw)


def test_journal_proposal_requires_explicit_unvalidated_and_unposted_state() -> None:
    raw = load(FIXTURES / "journal-proposal.unposted.json")
    JournalProposal.model_validate(raw)
    schema_validator("journal-proposal").validate(raw)
    for field in ("accounting_validation", "posting_status"):
        missing = copy.deepcopy(raw)
        del missing[field]
        assert_model_and_schema_reject(JournalProposal, "journal-proposal", missing)
    raw["posting_status"] = "POSTED"
    assert_model_and_schema_reject(JournalProposal, "journal-proposal", raw)


VALID_DIRECTED_AMOUNTS = [
    "1",
    "1250.00",
    "0.01",
    "0.0000000000000000000001",
    "9999999999999999999999999999999999999999.99",
]
INVALID_DIRECTED_AMOUNTS: list[object] = [
    "0",
    "0.0",
    "0.00",
    "-0",
    "-0.00",
    "-1",
    "-1250.00",
    "+1250.00",
    "1e3",
    "1,250.00",
    1250.0,
    1250,
]


@pytest.mark.parametrize("amount", VALID_DIRECTED_AMOUNTS)
@pytest.mark.parametrize(
    "model,schema_name,fixture,path",
    [
        (BankTransaction, "bank-transaction", "bank-transaction.normalized.json", ("money",)),
        (
            JournalProposal,
            "journal-proposal",
            "journal-proposal.unposted.json",
            ("lines", 0, "amount"),
        ),
    ],
)
def test_directed_money_accepts_only_exact_positive_strings(
    amount: str,
    model: type[BaseModel],
    schema_name: str,
    fixture: str,
    path: tuple[str | int, ...],
) -> None:
    raw = load(FIXTURES / fixture)
    target: Any = raw
    for segment in path:
        target = target[segment]
    target["amount"] = amount
    parsed = model.model_validate(raw)
    schema_validator(schema_name).validate(raw)
    assert amount in json.dumps(parsed.model_dump(mode="json"))


@pytest.mark.parametrize("amount", INVALID_DIRECTED_AMOUNTS)
@pytest.mark.parametrize(
    "model,schema_name,fixture,path",
    [
        (BankTransaction, "bank-transaction", "bank-transaction.normalized.json", ("money",)),
        (
            JournalProposal,
            "journal-proposal",
            "journal-proposal.unposted.json",
            ("lines", 0, "amount"),
        ),
    ],
)
def test_directed_money_rejects_ambiguous_or_nonpositive_values(
    amount: object,
    model: type[BaseModel],
    schema_name: str,
    fixture: str,
    path: tuple[str | int, ...],
) -> None:
    raw = load(FIXTURES / fixture)
    target: Any = raw
    for segment in path:
        target = target[segment]
    target["amount"] = amount
    assert_model_and_schema_reject(model, schema_name, raw)


JOB_FIXTURES = sorted(FIXTURES.glob("processing-job.*.json"))


@pytest.mark.parametrize("path", JOB_FIXTURES, ids=lambda path: path.name)
def test_every_job_state_fixture_has_model_schema_parity(path: Path) -> None:
    raw = load(path)
    ProcessingJob.model_validate(raw)
    schema_validator("processing-job").validate(raw)


@pytest.mark.parametrize(
    "fixture,mutation",
    [
        ("processing-job.retry-scheduled.json", {"retryable": False}),
        ("processing-job.retry-scheduled.json", {"retry_at": None}),
        ("processing-job.completed.json", {"completed_at": None}),
        (
            "processing-job.completed.json",
            {"error_code": "ACTIVE_ERROR", "safe_error_message": "Safe synthetic error"},
        ),
        ("processing-job.dead-lettered.json", {"retryable": True}),
        ("processing-job.processing.json", {"started_at": None}),
    ],
)
def test_representable_job_contradictions_fail_model_and_schema(
    fixture: str, mutation: dict[str, Any]
) -> None:
    raw = load(FIXTURES / fixture)
    raw.update(mutation)
    assert_model_and_schema_reject(ProcessingJob, "processing-job", raw)


@pytest.mark.parametrize(
    "fixture,mutation",
    [
        ("processing-job.processing.json", {"attempt_number": 4, "maximum_attempts": 3}),
        ("processing-job.processing.json", {"started_at": "2026-01-14T05:00:00Z"}),
        ("processing-job.processing.json", {"updated_at": "2026-01-14T05:00:00Z"}),
        ("processing-job.completed.json", {"completed_at": "2026-01-14T05:00:00Z"}),
        ("processing-job.failed.json", {"failed_at": "2026-01-14T05:00:00Z"}),
        ("processing-job.retry-scheduled.json", {"retry_at": "2026-01-15T05:00:00Z"}),
    ],
)
def test_job_cross_value_invariants_are_enforced_by_python_and_declared_in_schema(
    fixture: str, mutation: dict[str, Any]
) -> None:
    raw = load(FIXTURES / fixture)
    raw.update(mutation)
    with pytest.raises(ValidationError):
        ProcessingJob.model_validate(raw)
    extension = load(SCHEMAS / "processing-job.schema.json")["x-ledgerai-pydantic-invariants"]
    assert any(
        keyword in item
        for item in extension
        for keyword in ("timestamps", "retry_at", "attempt_number")
    )


def test_extraction_processing_completion_is_separate_from_review() -> None:
    valid = load(FIXTURES / "document-extraction.valid-invoice.json")
    assert valid["status"] == "COMPLETED"
    assert valid["review_disposition"] == "NOT_REQUIRED"
    DocumentExtraction.model_validate(valid)
    schema_validator("document-extraction").validate(valid)

    low = load(FIXTURES / "document-extraction.low-confidence.json")
    assert low["status"] == "COMPLETED"
    assert low["review_disposition"] == "REVIEW_REQUIRED"
    DocumentExtraction.model_validate(low)
    schema_validator("document-extraction").validate(low)


def test_critical_low_confidence_conflict_and_missing_require_review() -> None:
    cases: list[dict[str, Any]] = []
    low = load(FIXTURES / "document-extraction.low-confidence.json")
    low["review_disposition"] = "NOT_REQUIRED"
    low["review_reason_codes"] = []
    cases.append(low)

    conflict = load(FIXTURES / "document-extraction.valid-invoice.json")
    conflict["validation_issues"] = [
        {
            "code": "CONFLICTING_VALUES",
            "message": "Synthetic conflicting critical values",
            "field": "total",
            "severity": "ERROR",
        }
    ]
    cases.append(conflict)

    missing = load(FIXTURES / "document-extraction.valid-invoice.json")
    missing["fields"][0].update({"state": "MISSING", "value": None, "confidence": None})
    cases.append(missing)

    for raw in cases:
        assert_model_and_schema_reject(DocumentExtraction, "document-extraction", raw)


def test_missing_optional_field_does_not_require_review_and_human_review_is_explicit() -> None:
    optional = load(FIXTURES / "document-extraction.valid-invoice.json")
    optional["fields"].append(
        {
            "field_name": "purchase_order",
            "is_critical": False,
            "state": "MISSING",
            "value": None,
            "confidence": None,
            "provenance": [],
        }
    )
    DocumentExtraction.model_validate(optional)
    schema_validator("document-extraction").validate(optional)

    reviewed = load(FIXTURES / "document-extraction.low-confidence.json")
    reviewed["review_disposition"] = "REVIEWED"
    reviewed["review_reason_codes"] = ["HUMAN_REVIEW_COMPLETED"]
    DocumentExtraction.model_validate(reviewed)
    schema_validator("document-extraction").validate(reviewed)


DANGEROUS_MESSAGES = [
    "Traceback (most recent call last): secret failure",
    "postgresql://ledger:password@internal-db/ledger",
    r"C:\\Users\\operator\\secret.txt",
    "/var/lib/ledger/private.key",
    "Bearer eyJhbGciOiJIUzI1NiJ9.token",
    "-----BEGIN PRIVATE KEY-----",
    "SELECT account_number FROM bank_accounts",
    "SELECT * FROM users",
    "SELECT account_id, balance FROM ledger_entries",
    "INSERT INTO ledger_entries (account_id, balance) VALUES (1, 100)",
    "UPDATE ledger_entries SET balance = 0",
    "DELETE FROM ledger_entries WHERE account_id = 1",
    "DROP TABLE ledger_entries",
]

BENIGN_SAFE_MESSAGES = [
    "Please select a valid journal posting date from the calendar.",
    "Select an account from the list.",
    "Please choose a value from the available options.",
    "The selected date is outside the accounting period.",
    "The account source is not available for the selected date.",
    "please select the source document from the available options.",
    "THE SELECTED ACCOUNT IS OUTSIDE THE CURRENT PERIOD.",
]


@pytest.mark.parametrize("message", BENIGN_SAFE_MESSAGES)
@pytest.mark.parametrize("field_level", [False, True])
def test_error_envelope_accepts_safe_prose_with_selection_terms(
    message: str, field_level: bool
) -> None:
    raw = load(FIXTURES / "error.internal.json")
    if field_level:
        raw["field_errors"] = [{"field": "date", "code": "INVALID_DATE", "message": message}]
    else:
        raw["message"] = message
    ErrorEnvelope.model_validate(raw)
    schema_validator("error-envelope").validate(raw)


@pytest.mark.parametrize("message", DANGEROUS_MESSAGES)
@pytest.mark.parametrize("field_level", [False, True])
def test_error_envelope_rejects_obvious_internal_leakage(message: str, field_level: bool) -> None:
    raw = load(FIXTURES / "error.internal.json")
    if field_level:
        raw["field_errors"] = [{"field": "amount", "code": "INVALID", "message": message}]
    else:
        raw["message"] = message
    assert_model_and_schema_reject(ErrorEnvelope, "error-envelope", raw)


def test_error_envelope_has_safe_internal_diagnostic_reference() -> None:
    raw = load(FIXTURES / "error.internal.json")
    raw["internal_error_id"] = str(uuid4())
    parsed = ErrorEnvelope.model_validate(raw)
    schema_validator("error-envelope").validate(raw)
    assert parsed.internal_error_id is not None


def test_ci_contract_validation_is_read_only_and_complete() -> None:
    workflow = (ROOT / ".github" / "workflows" / "contracts.yml").read_text(encoding="utf-8")
    assert re.search(r"permissions:\s*\n\s+contents: read", workflow)
    assert "pull_request_target" not in workflow
    for command in (
        "ruff format --check .",
        "ruff check .",
        "mypy src tests tools",
        "pytest",
        "python tools/generate_contract_artifacts.py --check",
        "python -m compileall -q src tools tests",
    ):
        assert command in workflow
    for path in (
        "src/ledgerai_contracts/**",
        "tests/**",
        "tools/**",
        "shared/schemas/**",
        "shared/fixtures/**",
        "docs/architecture/**",
        "docs/integration/**",
        "pyproject.toml",
        ".github/workflows/contracts.yml",
    ):
        assert path in workflow
