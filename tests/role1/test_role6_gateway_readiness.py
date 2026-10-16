"""Model readiness verification tests evaluating Role 1 Document Intelligence.

Evaluates baseline model through Role 6 Gateway, verifies real provenance,
and tests adversarial robustness and training blockers.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from ledgerai_role1.evaluation.harness import EvaluationHarness
from ledgerai_role1.evaluation.hostile_evaluation import HostileDocumentEvaluator
from ledgerai_role1.evaluation.targets import ACCEPTANCE_TARGETS
from ledgerai_role1.governance.manifest import DatasetManifest
from ledgerai_role1.governance.split import verify_split_integrity
from ledgerai_role1.pipeline.adapters import Role6GatewayDocumentExtractor

MANIFEST_PATH = Path("data/manifests/nova_dataset_manifest.json")
UNSEEN_MANIFEST_PATH = Path("data/manifests/unseen_evaluation_manifest.json")
ROLE6_MANIFEST_PATH = Path("models/manifests/ledgerai_docintel_v1.manifest.json")
ERROR_REPORT_PATH = Path("docs/error_analysis_report.md")


def test_data_governance_gate_full_audit() -> None:
    """Audit dataset governance, split isolation, and cryptographic integrity."""
    # 1. Manifest file existence
    assert MANIFEST_PATH.exists(), f"Manifest file missing: {MANIFEST_PATH}"

    # 2. Manifest load and schema validity
    manifest = DatasetManifest.load_from_file(MANIFEST_PATH)

    # 3. Governance attributes
    assert manifest.dataset_name == "NOVA-Financial-Documents-Synthetic"
    assert manifest.version == "1.0.0"
    assert "Apache-2.0" in manifest.license
    assert manifest.redaction_policy != ""
    assert manifest.provenance_statement != ""

    # 4. Minimum sample size
    assert len(manifest.samples) >= 10, f"Insufficient sample size: {len(manifest.samples)}"

    # 5. Split counts
    split_counts = verify_split_integrity(manifest.samples)
    assert split_counts["train"] >= 5, f"Train count too low: {split_counts['train']}"
    assert split_counts["val"] >= 2, f"Val count too low: {split_counts['val']}"
    assert split_counts["test"] >= 5, f"Test count too low: {split_counts['test']}"

    # 6. Zero leakage across suppliers
    train_suppliers = {s.supplier_id for s in manifest.samples if s.split == "train"}
    val_suppliers = {s.supplier_id for s in manifest.samples if s.split == "val"}
    test_suppliers = {s.supplier_id for s in manifest.samples if s.split == "test"}
    assert train_suppliers.isdisjoint(val_suppliers), "Supplier leakage between train and val"
    assert train_suppliers.isdisjoint(test_suppliers), "Supplier leakage between train and test"
    assert val_suppliers.isdisjoint(test_suppliers), "Supplier leakage between val and test"

    # 7. Document coverage
    doc_types = {s.document_type.value for s in manifest.samples}
    assert "SUPPLIER_INVOICE" in doc_types
    assert "CUSTOMER_INVOICE" in doc_types
    assert "RECEIPT" in doc_types
    assert "BANK_STATEMENT" in doc_types
    assert "PURCHASE_ORDER" in doc_types

    # 8. Cryptographic hash verification of manifest
    raw_manifest = MANIFEST_PATH.read_bytes().replace(b"\r\n", b"\n")
    manifest_hash = hashlib.sha256(raw_manifest).hexdigest()
    assert manifest_hash == "9bf1d4a5695491061f8ddd558e2feae02617bdea138475e646d9bd476f80caa1"


def test_baseline_evaluation_through_role6_gateway() -> None:
    """Evaluate synthetic fixtures through Role 6 Model Runtime Gateway."""
    extractor = Role6GatewayDocumentExtractor()
    harness = EvaluationHarness(extractor=extractor)
    report = harness.evaluate_manifest(MANIFEST_PATH, split="test")

    # Sample size
    assert report.total_documents == 5
    assert report.total_valid_schema == 5

    # Target compliance
    assert report.invalid_schema_rate <= ACCEPTANCE_TARGETS["max_invalid_schema_rate"]
    assert report.decimal_amount_exact_match >= ACCEPTANCE_TARGETS["min_decimal_amount_exact_match"]
    assert report.date_accuracy >= ACCEPTANCE_TARGETS["min_date_accuracy"]
    assert report.currency_accuracy >= ACCEPTANCE_TARGETS["min_currency_accuracy"]
    assert report.line_item_accuracy >= ACCEPTANCE_TARGETS["min_line_item_accuracy"]

    # F1 score threshold
    f1_scores = [m.f1 for m in report.field_metrics.values()]
    avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    assert avg_f1 >= ACCEPTANCE_TARGETS["min_f1"]

    # Latency bound
    assert report.latency_seconds_mean <= 1.0


def test_unseen_evaluation_through_role6_gateway() -> None:
    """Evaluate representative unseen documents through Role 6 Model Runtime Gateway."""
    assert UNSEEN_MANIFEST_PATH.exists(), "Unseen evaluation manifest missing"
    extractor = Role6GatewayDocumentExtractor()
    harness = EvaluationHarness(extractor=extractor)
    report = harness.evaluate_manifest(UNSEEN_MANIFEST_PATH, split="test")

    assert report.total_documents == 10
    assert report.total_valid_schema == 10
    assert report.decimal_amount_exact_match == 1.0
    assert report.date_accuracy == 1.0
    assert report.currency_accuracy == 1.0
    assert report.unsupported_abstentions == 1

    # Missing fields must have 0% hallucination
    for fname, m in report.field_metrics.items():
        assert m.hallucination_rate == 0.0, f"Hallucination detected in {fname}"


def test_adversarial_hostile_documents_through_role6_gateway() -> None:
    """Evaluate adversarial robustness through Role 6 Model Runtime Gateway."""
    extractor = Role6GatewayDocumentExtractor()
    evaluator = HostileDocumentEvaluator(extractor=extractor)
    report = evaluator.evaluate_all()

    assert report.total_tests == 8
    assert report.passed_tests == 8
    assert report.pass_rate == 1.0

    for cat, res in report.by_category.items():
        assert res["passed"] == res["total"], f"Failed tests in category: {cat}"


def test_base_model_artifact_verification_and_blockers() -> None:
    """Verify base model artifact provenance, weight absence in git,
    and blocked training decision.
    """
    # 1. Model weights file must not exist in Git or on disk
    model_weight_path = Path("models/artifacts/model.safetensors")
    assert not model_weight_path.exists(), "Model weights file unexpectedly exists in repository"

    # 2. Manifest artifact hashes must match verified upstream SHA-256
    manifest_data = json.loads(ROLE6_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert (
        manifest_data["artifact_hashes"]["config.json"]
        == "422adefa19e62dd175961cec85bc0400344fe5bf9b22bd1182e05aaae78556e0"
    )
    assert (
        manifest_data["artifact_hashes"]["tokenizer.json"]
        == "cb63a0a23eef3d5b01063a9880a1925a65aaf4d1591d519910ee3527852950a0"
    )
    assert (
        manifest_data["artifact_hashes"]["model.safetensors.index.json"]
        == "260ab9fa1418d6d6ab79daa1d9da2c47264f3b72edb4630fc799077ac67d27c6"
    )

    # 3. Check verified immutable upstream git revision
    assert manifest_data["immutable_revision"] == "895c3a49bc3fa70a340399125c650a463535e71c"

    # 4. Error analysis report must classify result as INFRASTRUCTURE_READY_MODEL_BLOCKED
    assert ERROR_REPORT_PATH.exists(), f"Error report missing at {ERROR_REPORT_PATH}"
    report_content = ERROR_REPORT_PATH.read_text(encoding="utf-8")
    assert "INFRASTRUCTURE_READY_MODEL_BLOCKED" in report_content
    assert "TRAINING_REQUIRED_BUT_BLOCKED" in report_content
    assert "BASE_MODEL_WEIGHTS_NOT_IN_GIT" in report_content
    assert "DEMO_TRAINING_NOT_REQUIRED" in report_content


def test_git_ancestry_safety() -> None:
    """Verify commit 07b6601 is NOT an ancestor of main 91f5e03."""
    res = subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            "07b6601ecaa809e1bfda1e021ee3945c5bb54689",
            "91f5e036d8748c928aa7ca825fa3ce2ec4769e1f",
        ],
        capture_output=True,
    )
    assert res.returncode != 0, "Commit 07b6601 unexpectedly included in main"
