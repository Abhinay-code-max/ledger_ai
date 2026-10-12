"""Generate Role 3 OpenAPI, NOVA fixtures, expected graph, and labeled metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ledgerai_backend.reconciliation.api import create_reconciliation_app  # noqa: E402
from ledgerai_backend.reconciliation.contracts import (  # noqa: E402
    InvoiceFact,
    ReconciliationRequest,
    VersionedBankTransaction,
)
from ledgerai_backend.reconciliation.engine import ReconciliationEngine  # noqa: E402
from ledgerai_backend.reconciliation.security import Role3Security  # noqa: E402
from ledgerai_contracts.v1.common import (  # noqa: E402
    CorrelationMetadata,
    Money,
    PositiveMoney,
    ProvenanceReference,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext  # noqa: E402
from ledgerai_contracts.v1.transactions import BankTransaction, Counterparty  # noqa: E402

FIXTURE = ROOT / "shared" / "fixtures" / "reconciliation" / "v1" / "labeled-cases.json"
NAMESPACE = UUID("44202749-c18e-4a52-8467-04df546667c4")
TENANT = EntityTenantContext(
    tenant_id=uuid5(NAMESPACE, "tenant"),
    organization_id=uuid5(NAMESPACE, "organization"),
    legal_entity_id=uuid5(NAMESPACE, "legal-entity"),
)
STARTED = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)


def _id(kind: str, case: str, label: str) -> UUID:
    return uuid5(NAMESPACE, f"{kind}:{case}:{label}")


def _evidence(case: str, label: str, source: str) -> ProvenanceReference:
    return ProvenanceReference(
        source_document_id=_id("document", case, label),
        document_version="1",
        source_field=source,
        evidence_hash=hashlib.sha256(f"{case}:{label}:{source}".encode()).hexdigest(),
    )


def _request(case: dict[str, Any]) -> ReconciliationRequest:
    name = str(case["name"])
    invoices = [
        InvoiceFact(
            extraction_id=_id("invoice", name, item["label"]),
            extraction_version="1",
            document_id=_id("document", name, item["label"]),
            document_version="1",
            tenant_context=TENANT,
            amount=Money(amount=Decimal(str(item["amount"])), currency="INR"),
            invoice_date=date.fromisoformat(item.get("date", "2026-09-15")),
            expected_transaction_direction="DEBIT",
            reference=item["reference"],
            party_name="Synthetic Fixture Supplier",
            evidence_complete=True,
            content_fingerprint=hashlib.sha256(
                f"invoice:{name}:{item['label']}".encode()
            ).hexdigest(),
            provenance=[_evidence(name, item["label"], "invoice_total")],
        )
        for item in case["invoices"]
    ]
    transactions = [
        VersionedBankTransaction(
            transaction_version="1",
            transaction=BankTransaction(
                schema_version="1.0",
                transaction_id=_id("transaction", name, item["label"]),
                tenant_context=TENANT,
                bank_account_id=_id("bank-account", name, "primary"),
                import_batch_id=_id("batch", name, "primary"),
                source_row_number=index,
                booking_date=date.fromisoformat(item.get("date", "2026-09-15")),
                value_date=date.fromisoformat(item.get("date", "2026-09-15")),
                money=PositiveMoney(amount=Decimal(str(item["amount"])), currency="INR"),
                direction="DEBIT",
                narration="Synthetic labeled fixture",
                reference=item["reference"],
                counterparty=Counterparty(display_name="Synthetic Fixture Supplier"),
                external_source_id=f"SYNTH-{name}-{item['label']}",
                normalization_status="NORMALIZED",
                provenance=[_evidence(name, item["label"], "bank_row")],
                content_fingerprint=hashlib.sha256(
                    f"transaction:{name}:{item['label']}".encode()
                ).hexdigest(),
                correlation=CorrelationMetadata(
                    request_id=_id("request", name, "bank"),
                    correlation_id=_id("correlation", name, "flow"),
                ),
            ),
        )
        for index, item in enumerate(case["transactions"], start=1)
    ]
    return ReconciliationRequest(
        schema_version="1.0",
        tenant_context=TENANT,
        operation_id=_id("operation", name, "reconcile"),
        correlation_id=_id("correlation", name, "flow"),
        operation_started_at=STARTED,
        strategy_version="reconciliation-rules/1.0.0",
        invoices=invoices,
        transactions=transactions,
    )


def _edges(case: dict[str, Any], request: ReconciliationRequest) -> set[tuple[str, str]]:
    result = ReconciliationEngine().reconcile(request)
    if any(item.exception_type == "AMBIGUOUS_CANDIDATES" for item in result.exceptions):
        return set()
    invoice_labels = {
        invoice.extraction_id: case["invoices"][index]["label"]
        for index, invoice in enumerate(request.invoices)
    }
    transaction_labels = {
        item.transaction.transaction_id: case["transactions"][index]["label"]
        for index, item in enumerate(request.transactions)
    }
    selected_invoices = [
        invoice_labels[item.resource_id]
        for item in result.proposal.records
        if item.resource_type == "document_extraction"
    ]
    selected_transactions = [
        transaction_labels[item.resource_id]
        for item in result.proposal.records
        if item.resource_type == "bank_transaction"
    ]
    if result.proposal.match_type in {"UNMATCHED", "PARTIAL"}:
        return set()
    return {
        (invoice_label, transaction_label)
        for invoice_label in selected_invoices
        for transaction_label in selected_transactions
    }


def artifacts() -> dict[Path, str]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = data["cases"]
    true_positive = false_positive = false_negative = ambiguous = 0
    nova_request: ReconciliationRequest | None = None
    nova_result: Any = None
    for case in cases:
        operation = _request(case)
        result = ReconciliationEngine().reconcile(operation)
        predicted = _edges(case, operation)
        expected = {tuple(edge) for edge in case["expected_edges"]}
        true_positive += len(predicted & expected)
        false_positive += len(predicted - expected)
        false_negative += len(expected - predicted)
        detected_ambiguous = any(
            item.exception_type == "AMBIGUOUS_CANDIDATES" for item in result.exceptions
        )
        ambiguous += int(detected_ambiguous)
        assert detected_ambiguous is case["expected_ambiguous"]
        actual_exception_types = {item.exception_type for item in result.exceptions}
        assert set(case["expected_exceptions"]) <= actual_exception_types
        if case["name"] == "nova-planted-mismatch":
            nova_request, nova_result = operation, result
    precision = true_positive / (true_positive + false_positive or 1)
    recall = true_positive / (true_positive + false_negative or 1)
    metrics = {
        "fixture_version": data["fixture_version"],
        "labeled_case_count": len(cases),
        "true_positive_edges": true_positive,
        "false_positive_edges": false_positive,
        "false_negative_edges": false_negative,
        "precision": f"{precision:.4f}",
        "recall": f"{recall:.4f}",
        "ambiguity_rate": f"{ambiguous / len(cases):.4f}",
        "scope": "Synthetic labeled fixtures only; not a production accuracy claim.",
    }
    assert nova_request is not None and nova_result is not None
    nova_graph = {
        "fixture_version": data["fixture_version"],
        "proposal_id": str(nova_result.proposal.proposal_id),
        "match_type": nova_result.proposal.match_type,
        "status": nova_result.proposal.status,
        "records": [item.model_dump(mode="json") for item in nova_result.proposal.records],
        "expected_exception_types": sorted(
            {item.exception_type for item in nova_result.exceptions}
        ),
        "planted_exception": {
            "type": "AMOUNT_MISMATCH",
            "reason_code": "BATCH_AMOUNT_MISMATCH",
            "severity": "HIGH",
            "amount": "50.00",
            "currency": "INR",
            "blocks_posting": True,
            "blocks_close": True,
        },
    }
    app = create_reconciliation_app(Role3Security(secret="artifact-secret-32-bytes-minimum-value"))
    output_root = ROOT / "shared" / "fixtures" / "reconciliation" / "v1"
    return {
        ROOT / "shared" / "openapi" / "role3-v1.json": json.dumps(
            app.openapi(), indent=2, sort_keys=True
        )
        + "\n",
        output_root / "nova-request.json": json.dumps(
            nova_request.model_dump(mode="json"), indent=2, sort_keys=True
        )
        + "\n",
        output_root / "nova-expected-match-graph.json": json.dumps(
            nova_graph, indent=2, sort_keys=True
        )
        + "\n",
        output_root / "labeled-metrics.json": json.dumps(metrics, indent=2, sort_keys=True) + "\n",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale: list[str] = []
    rendered = artifacts()
    for path, content in rendered.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if stale:
        print("Stale Role 3 artifacts:\n" + "\n".join(stale))
        return 1
    print(f"{'Checked' if args.check else 'Generated'} {len(rendered)} Role 3 artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
