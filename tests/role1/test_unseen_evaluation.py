"""Tests verifying EvaluationHarness on representative unseen documents dataset."""

from __future__ import annotations

from pathlib import Path

from ledgerai_role1.evaluation.harness import EvaluationHarness
from ledgerai_role1.pipeline.adapters import Role6GatewayDocumentExtractor

UNSEEN_MANIFEST = Path("data/manifests/unseen_evaluation_manifest.json")


def test_unseen_evaluation_manifest_integrity_and_metrics() -> None:
    assert UNSEEN_MANIFEST.exists(), f"Unseen evaluation manifest missing at {UNSEEN_MANIFEST}"

    extractor = Role6GatewayDocumentExtractor()
    harness = EvaluationHarness(extractor=extractor)
    report = harness.evaluate_manifest(UNSEEN_MANIFEST, split="test")

    # 1. Total documents evaluated
    assert report.total_documents == 10

    # 2. Schema validity
    assert report.invalid_schema_rate == 0.0

    # 3. Accuracy metrics
    assert report.decimal_amount_exact_match == 1.0
    assert report.date_accuracy == 1.0
    assert report.currency_accuracy == 1.0
    assert report.line_item_accuracy == 1.0

    # 4. Abstention rate for negative controls (UNSEEN-MEMO-001)
    assert report.unsupported_abstentions == 1

    # 5. Hallucination rate on missing fields must be 0%
    for fname, m in report.field_metrics.items():
        assert m.hallucination_rate == 0.0, f"Unexpected hallucination in field {fname}"

    # 6. Mean latency bounds
    assert report.latency_seconds_mean < 1.0
