from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import jsonschema  # type: ignore[import-untyped]
import pytest

from ledgerai_contracts.v1.approvals import ApprovalDecision
from ledgerai_contracts.v1.audit import AuditEvent
from ledgerai_contracts.v1.documents import DocumentExtraction, DocumentMetadata
from ledgerai_contracts.v1.errors import ErrorEnvelope
from ledgerai_contracts.v1.events import EventEnvelope
from ledgerai_contracts.v1.exceptions import ExceptionRecord
from ledgerai_contracts.v1.jobs import ProcessingJob
from ledgerai_contracts.v1.journals import JournalProposal
from ledgerai_contracts.v1.policy import PolicyDecision
from ledgerai_contracts.v1.reconciliation import MatchProposal
from ledgerai_contracts.v1.transactions import BankTransaction

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "shared" / "fixtures" / "contracts" / "v1"
SCHEMAS = ROOT / "shared" / "schemas" / "v1"

MODEL_BY_PREFIX: list[tuple[str, type[Any], str]] = [
    ("approval-decision.", ApprovalDecision, "approval-decision"),
    ("audit-event.", AuditEvent, "audit-event"),
    ("bank-transaction.", BankTransaction, "bank-transaction"),
    ("document-extraction.", DocumentExtraction, "document-extraction"),
    ("document-metadata.", DocumentMetadata, "document-metadata"),
    ("error.", ErrorEnvelope, "error-envelope"),
    ("event.", EventEnvelope, "event-envelope"),
    ("exception.", ExceptionRecord, "exception"),
    ("journal-proposal.", JournalProposal, "journal-proposal"),
    ("match-proposal.", MatchProposal, "match-proposal"),
    ("policy-decision.", PolicyDecision, "policy-decision"),
    ("processing-job.", ProcessingJob, "processing-job"),
]


def load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def model_for(path: Path) -> tuple[type[Any], str]:
    for prefix, model, schema in MODEL_BY_PREFIX:
        if path.name.startswith(prefix):
            return model, schema
    raise AssertionError(f"unmapped fixture: {path.name}")


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.name)
def test_every_fixture_validates_against_model_and_schema(path: Path) -> None:
    raw = load(path)
    model, schema_name = model_for(path)
    model.model_validate(raw)
    jsonschema.Draft202012Validator(load(SCHEMAS / f"{schema_name}.schema.json")).validate(raw)


def test_generated_artifacts_are_current_and_deterministic() -> None:
    command = [sys.executable, "tools/generate_contract_artifacts.py", "--check"]
    first = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    second = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert first.returncode == second.returncode == 0, first.stdout + first.stderr
    assert first.stdout == second.stdout


def test_generated_money_schema_rejects_json_numbers() -> None:
    raw = load(FIXTURES / "bank-transaction.normalized.json")
    raw["money"]["amount"] = 1250.0
    schema = load(SCHEMAS / "bank-transaction.schema.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(raw)


def test_contract_import_has_no_backend_or_external_infrastructure_requirement() -> None:
    command = [
        sys.executable,
        "-c",
        f"import sys; sys.path.insert(0, {str(ROOT / 'src')!r}); "
        "import ledgerai_contracts; "
        "blocked={'boto3','psycopg','sqlalchemy','redis','fastapi'}; "
        "assert not blocked.intersection(sys.modules); print('ok')",
    ]
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_low_confidence_and_missing_states_are_explicit() -> None:
    extraction = DocumentExtraction.model_validate(
        load(FIXTURES / "document-extraction.low-confidence.json")
    )
    assert extraction.fields[0].state == "LOW_CONFIDENCE"
    assert extraction.fields[0].confidence is not None
    assert extraction.fields[1].state == "MISSING"
    assert extraction.fields[1].value is None


def test_journal_fixture_is_only_an_unposted_unvalidated_proposal() -> None:
    proposal = JournalProposal.model_validate(load(FIXTURES / "journal-proposal.unposted.json"))
    assert proposal.posting_status == "UNPOSTED"
    assert proposal.accounting_validation == "NOT_VALIDATED"
    assert not hasattr(proposal, "posted_journal_id")


def test_all_event_payloads_match_declared_type() -> None:
    for path in FIXTURES.glob("event.*.json"):
        event = EventEnvelope.model_validate(load(path))
        assert event.payload is not None
        assert type(event.payload) is EventEnvelope.PAYLOAD_MODELS[event.event_type]


def test_error_fixtures_do_not_leak_internal_details() -> None:
    forbidden = (
        "traceback",
        "select *",
        "password",
        "access_token",
        "secret=",
        "c:\\",
        "/var/",
        "localhost",
        "10.0.",
    )
    for path in FIXTURES.glob("error.*.json"):
        serialized = path.read_text(encoding="utf-8").lower()
        assert not any(token in serialized for token in forbidden), path.name


def test_fixtures_are_synthetic_and_have_no_obvious_secrets() -> None:
    serialized = "\n".join(path.read_text(encoding="utf-8") for path in FIXTURES.glob("*.json"))
    assert "NOVA TECHNOLOGIES PVT LTD" in serialized
    forbidden = ("BEGIN PRIVATE KEY", "AKIA", "ghp_", "sk_live_", "Bearer eyJ")
    assert not any(token in serialized for token in forbidden)


def test_cross_contract_identifiers_are_uuid_typed() -> None:
    extraction = DocumentExtraction.model_validate(
        load(FIXTURES / "document-extraction.valid-invoice.json")
    )
    document = DocumentMetadata.model_validate(load(FIXTURES / "document-metadata.valid.json"))
    transaction = BankTransaction.model_validate(
        load(FIXTURES / "bank-transaction.normalized.json")
    )
    assert extraction.document_id == document.document_id
    assert transaction.tenant_context == document.tenant_context
