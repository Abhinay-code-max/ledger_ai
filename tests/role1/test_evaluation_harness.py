"""Tests for evaluation metrics and harness."""

from __future__ import annotations

from pathlib import Path

from ledgerai_role1.evaluation.harness import EvaluationHarness
from ledgerai_role1.evaluation.metrics import character_error_rate, normalize_text, word_error_rate
from ledgerai_role1.training.lora_pipeline import LoRATrainingPipeline

MANIFEST_PATH = Path("data/manifests/nova_dataset_manifest.json")


def test_text_normalization_and_distance() -> None:
    assert normalize_text("  ACME   CORP.  ") == "acme corp"
    assert character_error_rate("ABC", "ABC") == 0.0
    assert character_error_rate("ABC", "ABD") == 1.0 / 3.0
    assert word_error_rate("Invoice Total", "Invoice Total") == 0.0


def test_evaluation_harness_test_split() -> None:
    harness = EvaluationHarness()
    report = harness.evaluate_manifest(MANIFEST_PATH, split="test")

    assert report.total_documents == 5
    assert report.invalid_schema_rate == 0.0
    assert report.decimal_amount_exact_match == 1.0
    assert report.currency_accuracy == 1.0
    assert report.date_accuracy == 1.0
    assert report.line_item_accuracy == 1.0

    passed, failures = harness.meets_acceptance_criteria(report)
    assert passed is True
    assert len(failures) == 0


def test_lora_training_pipeline_requires_justification() -> None:
    pipeline = LoRATrainingPipeline()
    import pytest

    with pytest.raises(RuntimeError, match="baseline model met acceptance targets"):
        pipeline.run(MANIFEST_PATH, justified=False)

    # When justified is True (e.g. for testing training pipeline execution)
    manifest = pipeline.run(MANIFEST_PATH, justified=True)
    assert manifest["model_name"] == "docintel-lora-adapter-v1"
    assert manifest["num_train_samples"] >= 5
    assert len(manifest["epoch_history"]) == 5
