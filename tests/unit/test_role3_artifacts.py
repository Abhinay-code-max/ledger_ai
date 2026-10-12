from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_fixture_metrics_are_explicitly_labeled_and_not_model_accuracy() -> None:
    path = ROOT / "shared" / "fixtures" / "reconciliation" / "v1" / "labeled-metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    assert metrics == {
        "ambiguity_rate": "0.1667",
        "false_negative_edges": 0,
        "false_positive_edges": 0,
        "fixture_version": "reconciliation-labeled/1.0.0",
        "labeled_case_count": 6,
        "precision": "1.0000",
        "recall": "1.0000",
        "scope": "Synthetic labeled fixtures only; not a production accuracy claim.",
        "true_positive_edges": 6,
    }


def test_nova_fixture_has_blocking_fifty_rupee_mismatch() -> None:
    path = ROOT / "shared" / "fixtures" / "reconciliation" / "v1" / "nova-expected-match-graph.json"
    graph = json.loads(path.read_text(encoding="utf-8"))
    assert graph["match_type"] == "ONE_TO_ONE"
    assert graph["status"] == "REVIEW_REQUIRED"
    assert graph["planted_exception"] == {
        "amount": "50.00",
        "blocks_close": True,
        "blocks_posting": True,
        "currency": "INR",
        "reason_code": "BATCH_AMOUNT_MISMATCH",
        "severity": "HIGH",
        "type": "AMOUNT_MISMATCH",
    }
