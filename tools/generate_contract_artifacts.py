"""Generate deterministic JSON Schemas and validated synthetic fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ledgerai_contracts.v1.accounting import (  # noqa: E402
    AccountingValidationResult,
    FinancialStatementRequest,
    FinancialStatementSnapshot,
    JournalPostingRequest,
    JournalPostingResult,
    PeriodCloseRequest,
    PeriodCloseResult,
    PeriodCloseValidationResult,
    PostingStatusResult,
    ProgressEvent,
    ProgressProjection,
    ProvenanceTrace,
)
from ledgerai_contracts.v1.approvals import ApprovalDecision  # noqa: E402
from ledgerai_contracts.v1.audit import AuditEvent  # noqa: E402
from ledgerai_contracts.v1.documents import DocumentExtraction, DocumentMetadata  # noqa: E402
from ledgerai_contracts.v1.errors import ErrorEnvelope  # noqa: E402
from ledgerai_contracts.v1.events import EVENT_REGISTRY, EventEnvelope  # noqa: E402
from ledgerai_contracts.v1.exceptions import ExceptionRecord  # noqa: E402
from ledgerai_contracts.v1.jobs import ProcessingJob  # noqa: E402
from ledgerai_contracts.v1.journals import JournalProposal  # noqa: E402
from ledgerai_contracts.v1.policy import PolicyDecision  # noqa: E402
from ledgerai_contracts.v1.reconciliation import MatchProposal  # noqa: E402
from ledgerai_contracts.v1.transactions import BankTransaction  # noqa: E402

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "accounting-validation-result": AccountingValidationResult,
    "approval-decision": ApprovalDecision,
    "audit-event": AuditEvent,
    "bank-transaction": BankTransaction,
    "document-extraction": DocumentExtraction,
    "document-metadata": DocumentMetadata,
    "error-envelope": ErrorEnvelope,
    "event-envelope": EventEnvelope,
    "financial-statement-request": FinancialStatementRequest,
    "financial-statement-snapshot": FinancialStatementSnapshot,
    "exception": ExceptionRecord,
    "journal-proposal": JournalProposal,
    "journal-posting-request": JournalPostingRequest,
    "journal-posting-result": JournalPostingResult,
    "match-proposal": MatchProposal,
    "policy-decision": PolicyDecision,
    "period-close-request": PeriodCloseRequest,
    "period-close-result": PeriodCloseResult,
    "period-close-validation-result": PeriodCloseValidationResult,
    "posting-status-result": PostingStatusResult,
    "processing-job": ProcessingJob,
    "progress-event": ProgressEvent,
    "progress-projection": ProgressProjection,
    "provenance-trace": ProvenanceTrace,
}

U = {
    "tenant": "00000000-0000-4000-8000-000000000001",
    "org": "00000000-0000-4000-8000-000000000002",
    "entity": "00000000-0000-4000-8000-000000000003",
    "request": "00000000-0000-4000-8000-000000000004",
    "correlation": "00000000-0000-4000-8000-000000000005",
    "document": "00000000-0000-4000-8000-000000000010",
    "extraction": "00000000-0000-4000-8000-000000000011",
    "transaction": "00000000-0000-4000-8000-000000000012",
    "batch": "00000000-0000-4000-8000-000000000013",
    "bank": "00000000-0000-4000-8000-000000000014",
    "match": "00000000-0000-4000-8000-000000000015",
    "exception": "00000000-0000-4000-8000-000000000016",
    "journal": "00000000-0000-4000-8000-000000000017",
    "policy": "00000000-0000-4000-8000-000000000018",
    "policy_set": "00000000-0000-4000-8000-000000000019",
    "approval": "00000000-0000-4000-8000-000000000020",
    "approval_request": "00000000-0000-4000-8000-000000000021",
    "job": "00000000-0000-4000-8000-000000000022",
    "period": "00000000-0000-4000-8000-000000000023",
    "workflow": "00000000-0000-4000-8000-000000000024",
    "audit": "00000000-0000-4000-8000-000000000025",
    "operation": "00000000-0000-4000-8000-000000000026",
    "snapshot": "00000000-0000-4000-8000-000000000027",
    "posted_journal": "00000000-0000-4000-8000-000000000028",
    "progress": "00000000-0000-4000-8000-000000000029",
}
TS = "2026-01-15T10:30:00+05:30"
UTC_TS = "2026-01-15T05:00:00Z"
HASH = "a" * 64
TENANT = {"tenant_id": U["tenant"], "organization_id": U["org"], "legal_entity_id": U["entity"]}
CORRELATION = {"request_id": U["request"], "correlation_id": U["correlation"], "causation_id": None}
SERVICE = {"producer_type": "SERVICE", "name": "ledgerai-contract-fixture", "version": "1.0.0"}
MODEL = {
    "producer_type": "MODEL",
    "name": "synthetic-extraction-agent",
    "version": "1.0.0",
    "model_name": "fixture-model",
    "model_version": "synthetic-v1",
    "prompt_template_version": "invoice-v1",
}
PROVENANCE = {
    "source_document_id": U["document"],
    "document_version": "obj-v1",
    "page_number": 1,
    "source_field": "invoice_total",
    "extraction_version": "synthetic-v1",
    "confidence": "0.98",
    "evidence_hash": HASH,
}


def ref(kind: str, identifier: str, version: str | None = "1") -> dict[str, Any]:
    return {"resource_type": kind, "resource_id": identifier, "resource_version": version}


DOCUMENT = {
    "schema_version": "1.0",
    "document_id": U["document"],
    "tenant_context": TENANT,
    "storage": {"object_key": "tenant-fixture/invoices/invoice-001", "storage_version": "obj-v1"},
    "original_filename": "NOVA_TECH_SYNTHETIC_INVOICE_001.pdf",
    "detected_media_type": "application/pdf",
    "byte_size": 48231,
    "content_hash": HASH,
    "hash_algorithm": "SHA-256",
    "document_category": "INVOICE",
    "upload_actor": {"actor_type": "HUMAN", "actor_id": "fixture.user@nova.invalid"},
    "uploaded_at": TS,
    "lifecycle_status": "READY",
    "correlation": CORRELATION,
}


def extracted_field(
    name: str, value: Any, confidence: str = "0.98", *, is_critical: bool = True
) -> dict[str, Any]:
    return {
        "field_name": name,
        "is_critical": is_critical,
        "state": "EXTRACTED",
        "value": value,
        "confidence": confidence,
        "provenance": [PROVENANCE],
    }


EXTRACTION = {
    "schema_version": "1.0",
    "extraction_id": U["extraction"],
    "document_id": U["document"],
    "document_version": "obj-v1",
    "tenant_context": TENANT,
    "classification": "INVOICE",
    "fields": [
        extracted_field("supplier_name", "NOVA TECHNOLOGIES PVT LTD"),
        extracted_field("invoice_number", "SYNTH-INV-001"),
        extracted_field("invoice_date", "2026-01-14"),
        extracted_field("total", {"amount": "1250.00", "currency": "INR"}),
    ],
    "line_items": [],
    "validation_issues": [],
    "status": "COMPLETED",
    "review_disposition": "NOT_REQUIRED",
    "review_reason_codes": [],
    "producer": MODEL,
    "created_at": TS,
    "updated_at": TS,
    "correlation": CORRELATION,
}

LOW_CONFIDENCE_EXTRACTION = {
    **EXTRACTION,
    "extraction_id": "00000000-0000-4000-8000-000000000111",
    "fields": [
        {
            "field_name": "supplier_tax_id",
            "is_critical": True,
            "state": "LOW_CONFIDENCE",
            "value": "SYNTHETIC-UNCERTAIN",
            "confidence": "0.31",
            "provenance": [{**PROVENANCE, "confidence": "0.31", "source_field": "supplier_tax_id"}],
        },
        {
            "field_name": "purchase_order",
            "is_critical": False,
            "state": "MISSING",
            "value": None,
            "confidence": None,
            "provenance": [],
        },
    ],
    "validation_issues": [
        {
            "code": "LOW_CONFIDENCE_FIELD",
            "message": "Synthetic field requires review",
            "field": "supplier_tax_id",
            "severity": "WARNING",
        }
    ],
    "status": "COMPLETED",
    "review_disposition": "REVIEW_REQUIRED",
    "review_reason_codes": ["CRITICAL_FIELD_LOW_CONFIDENCE"],
}

TRANSACTION = {
    "schema_version": "1.0",
    "transaction_id": U["transaction"],
    "tenant_context": TENANT,
    "bank_account_id": U["bank"],
    "import_batch_id": U["batch"],
    "source_row_number": 2,
    "booking_date": "2026-01-15",
    "value_date": "2026-01-14",
    "money": {"amount": "1250.00", "currency": "INR"},
    "direction": "DEBIT",
    "narration": "SYNTHETIC NOVA TECHNOLOGIES PVT LTD INVOICE",
    "reference": "SYNTH-INV-001",
    "counterparty": {
        "display_name": "Synthetic Supplies Ltd",
        "masked_account_reference": "XXXX0012",
    },
    "external_source_id": "SYNTH-TXN-001",
    "normalization_status": "NORMALIZED",
    "provenance": [{**PROVENANCE, "source_row": 2, "page_number": None}],
    "content_fingerprint": "b" * 64,
    "correlation": CORRELATION,
}

MATCH = {
    "schema_version": "1.0",
    "proposal_id": U["match"],
    "proposal_version": 1,
    "tenant_context": TENANT,
    "records": [
        ref("bank_transaction", U["transaction"]),
        ref("document_extraction", U["extraction"]),
    ],
    "match_type": "ONE_TO_ONE",
    "confidence": "0.97",
    "score": "0.97",
    "reasons": [
        {
            "code": "AMOUNT_AND_REFERENCE_MATCH",
            "explanation": "Synthetic amount and reference agree",
            "contribution": "0.90",
        }
    ],
    "conflicts": [],
    "producer": {**SERVICE, "algorithm_version": "match-fixture-v1"},
    "status": "PROPOSED",
    "created_at": TS,
    "updated_at": TS,
    "correlation": CORRELATION,
    "provenance": [PROVENANCE],
}

EXCEPTION = {
    "schema_version": "1.0",
    "exception_id": U["exception"],
    "tenant_context": TENANT,
    "exception_type": "AMOUNT_MISMATCH",
    "severity": "HIGH",
    "involved_resources": [
        ref("bank_transaction", U["transaction"]),
        ref("document_extraction", U["extraction"]),
    ],
    "explanation": "Synthetic transaction and invoice totals differ.",
    "reason_codes": ["AMOUNT_MISMATCH"],
    "supporting_evidence": [PROVENANCE],
    "suggested_action": "Review source evidence",
    "required_action": "HUMAN_REVIEW",
    "resolution_status": "OPEN",
    "resolution_reference": None,
    "detector": {**SERVICE, "rule_or_policy_version": "exception-rules-v1"},
    "created_at": TS,
    "updated_at": TS,
    "correlation": CORRELATION,
}

JOURNAL = {
    "schema_version": "1.0",
    "proposal_id": U["journal"],
    "proposal_version": 1,
    "tenant_context": TENANT,
    "proposed_journal_date": "2026-01-15",
    "currency": "INR",
    "lines": [
        {
            "line_id": "00000000-0000-4000-8000-000000000171",
            "account_reference": "SYNTH-EXPENSE",
            "direction": "DEBIT",
            "amount": {"amount": "1250.00", "currency": "INR"},
            "description": "Synthetic expense",
            "source_evidence": [PROVENANCE],
        },
        {
            "line_id": "00000000-0000-4000-8000-000000000172",
            "account_reference": "SYNTH-PAYABLE",
            "direction": "CREDIT",
            "amount": {"amount": "1250.00", "currency": "INR"},
            "description": "Synthetic payable",
            "source_evidence": [PROVENANCE],
        },
    ],
    "source_evidence": [PROVENANCE],
    "explanation": "Synthetic balanced-looking proposal; not posted and not validated by Role 2.",
    "confidence": "0.88",
    "producer": MODEL,
    "policy_decision": None,
    "approval_decision": None,
    "accounting_validation": "NOT_VALIDATED",
    "posting_status": "UNPOSTED",
    "correlation": CORRELATION,
}

POLICY = {
    "schema_version": "1.0",
    "decision_id": U["policy"],
    "tenant_context": TENANT,
    "subject": ref("journal_proposal", U["journal"]),
    "policy_set_id": U["policy_set"],
    "policy_set_version": "2026.01",
    "outcome": "REVIEW_REQUIRED",
    "evaluated_inputs": {"confidence": "0.88", "amount": "1250.00"},
    "matched_rule_ids": ["REVIEW_AI_CLASSIFIED_ACCOUNT"],
    "reason_codes": ["AI_CLASSIFICATION_REQUIRES_REVIEW"],
    "explanation": "Synthetic AI classification requires a human decision.",
    "evaluator_version": "policy-evaluator-v1",
    "decided_at": TS,
    "correlation": CORRELATION,
}


def approval(action: str, identifier: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "decision_id": identifier,
        "tenant_context": TENANT,
        "approval_request_id": U["approval_request"],
        "reviewed_resource": ref("journal_proposal", U["journal"]),
        "actor": {"actor_type": "HUMAN", "actor_id": "fixture.reviewer@nova.invalid"},
        "action": action,
        "reason": "Synthetic fixture decision",
        "structured_corrections": None,
        "authorization_roles": ["LEDGER_REVIEWER"],
        "separation_of_duties_checked": True,
        "separation_of_duties_rule": "REQUESTER_CANNOT_APPROVE",
        "decided_at": TS,
        "correlation": CORRELATION,
    }


APPROVAL = approval("APPROVE", U["approval"])
REJECTED_APPROVAL = approval("REJECT", "00000000-0000-4000-8000-000000000120")

AUDIT = {
    "schema_version": "1.0",
    "audit_event_id": U["audit"],
    "tenant_context": TENANT,
    "actor": {"actor_type": "HUMAN", "actor_id": "fixture.reviewer@nova.invalid"},
    "action": "APPROVAL_DECIDED",
    "resource_type": "journal_proposal",
    "resource_id": U["journal"],
    "resource_version": "1",
    "before_hash": None,
    "after_hash": "c" * 64,
    "correlation": CORRELATION,
    "producer_versions": [SERVICE],
    "schema_versions": ["1.0"],
    "rule_versions": ["REQUESTER_CANNOT_APPROVE"],
    "policy_versions": ["2026.01"],
    "outcome": "SUCCEEDED",
    "occurred_at": TS,
    "source_ip": None,
    "client_metadata": None,
}


def job(state: str, index: int) -> dict[str, Any]:
    failed_attempt = state in {"RETRY_SCHEDULED", "FAILED", "DEAD_LETTERED"}
    value: dict[str, Any] = {
        "schema_version": "1.0",
        "job_id": f"00000000-0000-4000-8000-{220 + index:012d}",
        "tenant_context": TENANT,
        "job_type": "DOCUMENT_EXTRACTION",
        "state": state,
        "attempt_number": 0 if state == "QUEUED" else (3 if state == "DEAD_LETTERED" else 1),
        "maximum_attempts": 3,
        "input_references": [ref("document", U["document"], "obj-v1")],
        "output_references": [],
        "progress_percent": 50
        if state == "PROCESSING"
        else (100 if state in {"COMPLETED", "REVIEW_REQUIRED"} else None),
        "retryable": state in {"RETRY_SCHEDULED", "FAILED"},
        "error_code": "SYNTHETIC_DOWNSTREAM_FAILURE" if failed_attempt else None,
        "safe_error_message": "Synthetic processing failure" if failed_attempt else None,
        "queue_name": "document-processing",
        "scheduled_for": UTC_TS,
        "correlation": CORRELATION,
        "created_at": TS,
        "started_at": TS if state != "QUEUED" else None,
        "updated_at": TS,
        "completed_at": TS if state == "COMPLETED" else None,
        "retry_at": "2026-01-15T05:05:00Z" if state == "RETRY_SCHEDULED" else None,
        "failed_at": TS if failed_attempt else None,
    }
    return value


JOB_STATES = [
    "QUEUED",
    "PROCESSING",
    "RETRY_SCHEDULED",
    "REVIEW_REQUIRED",
    "COMPLETED",
    "FAILED",
    "DEAD_LETTERED",
]

ERROR_CATEGORIES = [
    "INPUT_VALIDATION",
    "AUTHENTICATION",
    "AUTHORIZATION",
    "CONFLICT",
    "STATE_TRANSITION",
    "RATE_LIMIT",
    "DOWNSTREAM",
    "INTERNAL",
]


def error(category: str, index: int) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "category": category,
        "code": f"SYNTHETIC_{category}",
        "message": "The synthetic request could not be completed.",
        "request_id": f"00000000-0000-4000-8000-{400 + index:012d}",
        "correlation_id": U["correlation"],
        "field_errors": (
            [{"field": "amount", "code": "INVALID_DECIMAL", "message": "Use a decimal string."}]
            if category == "INPUT_VALIDATION"
            else []
        ),
        "retryable": category in {"RATE_LIMIT", "DOWNSTREAM", "INTERNAL"},
        "help_reference": "urn:ledgerai:errors:v1",
    }


RESOURCE_EVENT_REFS = {
    "document.validated.v1": ref("document", U["document"], "obj-v1"),
    "journal.posting.requested.v1": ref("journal_proposal", U["journal"]),
    "journal.posted.v1": ref("posted_journal", "00000000-0000-4000-8000-000000000301"),
    "period.close.requested.v1": ref("accounting_period", U["period"]),
    "period.closed.v1": ref("accounting_period", U["period"]),
}


def event_payload(event_type: str) -> dict[str, Any]:
    payloads: dict[str, dict[str, Any]] = {
        "document.uploaded.v1": {"document": DOCUMENT},
        "document.extraction.requested.v1": {
            "document": ref("document", U["document"], "obj-v1"),
            "job": ref("processing_job", U["job"]),
        },
        "document.extracted.v1": {"extraction": EXTRACTION},
        "transactions.imported.v1": {
            "import_batch": ref("import_batch", U["batch"]),
            "transaction_count": 1,
        },
        "reconciliation.requested.v1": {
            "request": ref("reconciliation_request", "00000000-0000-4000-8000-000000000302"),
            "transaction_ids": [U["transaction"]],
        },
        "reconciliation.proposed.v1": {"proposal": MATCH},
        "exception.created.v1": {"exception": EXCEPTION},
        "journal.proposal.created.v1": {"proposal": JOURNAL},
        "policy.evaluated.v1": {"decision": POLICY},
        "approval.requested.v1": {
            "approval_request": ref("approval_request", U["approval_request"]),
            "subject": ref("journal_proposal", U["journal"]),
        },
        "approval.decided.v1": {"decision": APPROVAL},
        "workflow.failed.v1": {
            "workflow": ref("workflow", U["workflow"]),
            "error_code": "SYNTHETIC_FAILURE",
            "safe_message": "Synthetic workflow needs attention.",
            "retryable": False,
        },
    }
    if event_type in RESOURCE_EVENT_REFS:
        return {"resource": RESOURCE_EVENT_REFS[event_type]}
    return payloads[event_type]


EVENT_TYPES = list(EVENT_REGISTRY)


def event(event_type: str, index: int) -> dict[str, Any]:
    return {
        "event_id": f"00000000-0000-4000-8000-{600 + index:012d}",
        "event_type": event_type,
        "schema_version": "1.0",
        "occurred_at": TS,
        "tenant_context": TENANT,
        "correlation_id": U["correlation"],
        "causation_id": None,
        "producer": SERVICE,
        "payload": event_payload(event_type),
        "payload_reference": None,
        "trace_context": {"traceparent": "00-00000000000000000000000000000001-0000000000000001-01"},
    }


POSTING_REQUEST = {
    "schema_version": "1.0",
    "tenant_context": TENANT,
    "operation_id": U["operation"],
    "proposal": ref("journal_proposal", U["journal"]),
    "proposal_version": 1,
    "accounting_period_id": U["period"],
    "requested_at": TS,
    "producer": SERVICE,
    "correlation": CORRELATION,
}
ACCOUNTING_VALIDATION = {
    "schema_version": "1.0",
    "tenant_context": TENANT,
    "operation_id": U["operation"],
    "proposal_id": U["journal"],
    "proposal_version": 1,
    "outcome": "VALIDATED",
    "issues": [],
    "producer": SERVICE,
    "correlation": CORRELATION,
}
POSTING_RESULT = {
    "schema_version": "1.0",
    "tenant_context": TENANT,
    "operation_id": U["operation"],
    "proposal_id": U["journal"],
    "proposal_version": 1,
    "outcome": "POSTED",
    "posted_journal_id": U["posted_journal"],
    "posted_at": TS,
    "ledger_references": [ref("posted_journal", U["posted_journal"])],
    "issues": [],
    "producer": SERVICE,
    "correlation": CORRELATION,
}
POSTING_STATUS = {
    **POSTING_RESULT,
    "outcome": "IN_PROGRESS",
    "posted_journal_id": None,
    "posted_at": None,
    "ledger_references": [],
}
PERIOD_CLOSE_REQUEST = {
    "schema_version": "1.0",
    "tenant_context": TENANT,
    "operation_id": U["operation"],
    "accounting_period_id": U["period"],
    "period_start": "2026-01-01",
    "period_end": "2026-01-31",
    "requested_at": TS,
    "producer": SERVICE,
    "correlation": CORRELATION,
}
PERIOD_CLOSE_VALIDATION = {
    "schema_version": "1.0",
    "tenant_context": TENANT,
    "operation_id": U["operation"],
    "accounting_period_id": U["period"],
    "outcome": "VALIDATED",
    "issues": [],
    "producer": SERVICE,
    "correlation": CORRELATION,
}
PERIOD_CLOSE_RESULT = {
    "schema_version": "1.0",
    "tenant_context": TENANT,
    "operation_id": U["operation"],
    "accounting_period_id": U["period"],
    "outcome": "CLOSED",
    "issues": [],
    "closed_at": TS,
    "producer": SERVICE,
    "correlation": CORRELATION,
}
STATEMENT_REQUEST = {
    "schema_version": "1.0",
    "tenant_context": TENANT,
    "operation_id": U["operation"],
    "accounting_period_id": U["period"],
    "statement_type": "TRIAL_BALANCE",
    "as_of": TS,
    "correlation": CORRELATION,
}
STATEMENT_SNAPSHOT = {
    "schema_version": "1.0",
    "snapshot_id": U["snapshot"],
    "tenant_context": TENANT,
    "accounting_period_id": U["period"],
    "statement_type": "TRIAL_BALANCE",
    "currency": "INR",
    "as_of": TS,
    "status": "AVAILABLE",
    "lines": [
        {
            "line_id": "cash",
            "account_reference": "1100",
            "label": "Cash",
            "amount": {"amount": "1250.00", "currency": "INR"},
            "ledger_references": [ref("posted_journal", U["posted_journal"])],
        }
    ],
    "producer": SERVICE,
    "correlation": CORRELATION,
}
PROVENANCE_TRACE = {
    "schema_version": "1.0",
    "tenant_context": TENANT,
    "root": ref("journal_proposal", U["journal"]),
    "nodes": [ref("journal_proposal", U["journal"]), ref("posted_journal", U["posted_journal"])],
    "edges": [
        {
            "source": ref("journal_proposal", U["journal"]),
            "target": ref("posted_journal", U["posted_journal"]),
            "relation": "POSTED_AS",
        }
    ],
    "missing_references": [],
}
PROGRESS_EVENT = {
    "schema_version": "1.0",
    "event_id": U["progress"],
    "tenant_context": TENANT,
    "resource": ref("posting_operation", U["operation"], "2"),
    "stage": "JOURNAL_POSTING",
    "status": "IN_PROGRESS",
    "occurred_at": TS,
    "correlation_id": U["correlation"],
    "percent": 50,
    "reason_code": None,
}
PROGRESS_PROJECTION = {
    "schema_version": "1.0",
    "tenant_context": TENANT,
    "resource": ref("posting_operation", U["operation"], "2"),
    "stage": "JOURNAL_POSTING",
    "status": "IN_PROGRESS",
    "last_event_id": U["progress"],
    "occurred_at": TS,
    "correlation_id": U["correlation"],
    "percent": 50,
    "reason_code": None,
}


CONTRACT_FIXTURES: list[tuple[str, type[Any], dict[str, Any]]] = [
    (
        "accounting-validation-result.validated.json",
        AccountingValidationResult,
        ACCOUNTING_VALIDATION,
    ),
    ("document-metadata.valid.json", DocumentMetadata, DOCUMENT),
    ("document-extraction.valid-invoice.json", DocumentExtraction, EXTRACTION),
    ("document-extraction.low-confidence.json", DocumentExtraction, LOW_CONFIDENCE_EXTRACTION),
    ("bank-transaction.normalized.json", BankTransaction, TRANSACTION),
    ("match-proposal.high-confidence.json", MatchProposal, MATCH),
    ("exception.amount-mismatch.json", ExceptionRecord, EXCEPTION),
    ("journal-proposal.unposted.json", JournalProposal, JOURNAL),
    ("policy-decision.review-required.json", PolicyDecision, POLICY),
    ("approval-decision.approved.json", ApprovalDecision, APPROVAL),
    ("approval-decision.rejected.json", ApprovalDecision, REJECTED_APPROVAL),
    ("audit-event.approval.json", AuditEvent, AUDIT),
    (
        "financial-statement-request.trial-balance.json",
        FinancialStatementRequest,
        STATEMENT_REQUEST,
    ),
    ("financial-statement-snapshot.available.json", FinancialStatementSnapshot, STATEMENT_SNAPSHOT),
    ("journal-posting-request.valid.json", JournalPostingRequest, POSTING_REQUEST),
    ("journal-posting-result.posted.json", JournalPostingResult, POSTING_RESULT),
    ("period-close-request.valid.json", PeriodCloseRequest, PERIOD_CLOSE_REQUEST),
    ("period-close-result.closed.json", PeriodCloseResult, PERIOD_CLOSE_RESULT),
    (
        "period-close-validation-result.validated.json",
        PeriodCloseValidationResult,
        PERIOD_CLOSE_VALIDATION,
    ),
    ("posting-status-result.in-progress.json", PostingStatusResult, POSTING_STATUS),
    ("progress-event.posting.json", ProgressEvent, PROGRESS_EVENT),
    ("progress-projection.posting.json", ProgressProjection, PROGRESS_PROJECTION),
    ("provenance-trace.posting.json", ProvenanceTrace, PROVENANCE_TRACE),
]
CONTRACT_FIXTURES += [
    (f"processing-job.{state.lower().replace('_', '-')}.json", ProcessingJob, job(state, i))
    for i, state in enumerate(JOB_STATES)
]
CONTRACT_FIXTURES += [
    (f"error.{category.lower().replace('_', '-')}.json", ErrorEnvelope, error(category, i))
    for i, category in enumerate(ERROR_CATEGORIES)
]
EVENT_FIXTURES = [
    (f"event.{event_type}.json", EventEnvelope, event(event_type, i))
    for i, event_type in enumerate(EVENT_TYPES)
]


def render_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def artifact_map() -> dict[Path, str]:
    artifacts: dict[Path, str] = {}
    schema_dir = ROOT / "shared" / "schemas" / "v1"
    fixture_dir = ROOT / "shared" / "fixtures" / "contracts" / "v1"
    for name, model in SCHEMA_MODELS.items():
        artifacts[schema_dir / f"{name}.schema.json"] = render_json(model.model_json_schema())
    for filename, model, raw in CONTRACT_FIXTURES + EVENT_FIXTURES:
        validated = model.model_validate(raw)
        artifacts[fixture_dir / filename] = render_json(validated.model_dump(mode="json"))
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if checked-in artifacts differ")
    args = parser.parse_args()
    stale: list[str] = []
    for path, content in artifact_map().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if stale:
        print("Generated contract artifacts are stale:")
        print("\n".join(stale))
        return 1
    print(f"{'Checked' if args.check else 'Generated'} {len(artifact_map())} contract artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
