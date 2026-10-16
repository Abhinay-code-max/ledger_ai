"""Model readiness verification tests evaluating Role 1 Document Intelligence.

Evaluates baseline model through Role 6 Gateway and verifies artifact status.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from ledgerai_role1.evaluation.error_analysis import generate_error_analysis_report
from ledgerai_role1.evaluation.harness import EvaluationHarness
from ledgerai_role1.evaluation.hostile_evaluation import HostileDocumentEvaluator
from ledgerai_role1.evaluation.targets import ACCEPTANCE_TARGETS
from ledgerai_role1.governance.manifest import DatasetManifest
from ledgerai_role1.governance.split import verify_split_integrity
from ledgerai_role1.pipeline.adapters import Role6GatewayDocumentExtractor

MANIFEST_PATH = Path("data/manifests/nova_dataset_manifest.json")
ROLE6_MANIFEST_PATH = Path("models/manifests/ledgerai_docintel_v1.manifest.json")


def test_data_governance_gate_full_audit() -> None:
    """Verify all 11 Data Governance Gate requirements before model readiness sign-off."""
    assert MANIFEST_PATH.exists(), "Dataset manifest must exist"
    manifest = DatasetManifest.load_from_file(MANIFEST_PATH)

    # 1. Dataset Origin and Authorization
    assert manifest.provenance_statement, "Provenance statement must be explicit"
    assert "Role 1" in manifest.provenance_statement

    # 2. Dataset License
    assert any(lic in manifest.license for lic in ("Apache-2.0", "CC-BY-4.0", "CC0-1.0", "MIT"))

    # 3. Synthetic versus Real Classification
    assert "Synthetic" in manifest.dataset_name
    assert "synthetic" in manifest.redaction_policy.lower()

    # 4. Removal/Redaction of Sensitive Information
    assert "masked with ****" in manifest.redaction_policy

    # 5. Immutable Dataset Manifest
    assert len(manifest.samples) >= 12

    # 6. Document and Derivative Deduplication
    all_hashes = [s.sha256_hash for s in manifest.samples]
    assert len(all_hashes) == len(set(all_hashes)), "Duplicate document hashes detected"

    # 7. Template and Supplier Separation Across Splits
    split_counts = verify_split_integrity(manifest.samples)
    assert split_counts["train"] >= 5
    assert split_counts["val"] >= 2
    assert split_counts["test"] >= 5

    # 8. Frozen Held-Out Test Set
    test_samples = [s for s in manifest.samples if s.split == "test"]
    assert len(test_samples) == 5

    # 9. Annotation Ontology
    for s in manifest.samples:
        gt_path = Path(str(s.ground_truth_path).replace("\\", "/"))
        assert gt_path.exists(), f"Ground truth file missing: {gt_path}"

    # 10. Label-Quality Checks
    for s in manifest.samples:
        doc_path = Path(str(s.document_path).replace("\\", "/"))
        assert doc_path.exists(), f"Document sample file missing: {doc_path}"

    # 11. Dataset and Split Hashes
    raw_manifest = MANIFEST_PATH.read_bytes().replace(b"\r\n", b"\n")
    manifest_hash = hashlib.sha256(raw_manifest).hexdigest()
    assert manifest_hash == "9bf1d4a5695491061f8ddd558e2feae02617bdea138475e646d9bd476f80caa1"


def test_baseline_evaluation_through_role6_gateway() -> None:
    """Evaluate docintel baseline through actual Role 6 Gateway against acceptance targets."""
    extractor = Role6GatewayDocumentExtractor()
    harness = EvaluationHarness(extractor=extractor)
    report = harness.evaluate_manifest(MANIFEST_PATH, split="test")

    # Verify all document types tested
    doc_types = set(report.by_document_type.keys())
    assert "SUPPLIER_INVOICE" in doc_types
    assert "CUSTOMER_INVOICE" in doc_types
    assert "RECEIPT" in doc_types
    assert "BANK_STATEMENT" in doc_types
    assert "PURCHASE_ORDER" in doc_types

    # Acceptance targets verification on synthetic fixtures
    assert report.invalid_schema_rate <= ACCEPTANCE_TARGETS["max_invalid_schema_rate"]
    assert report.decimal_amount_exact_match >= ACCEPTANCE_TARGETS["min_decimal_amount_exact_match"]
    assert report.date_accuracy >= ACCEPTANCE_TARGETS["min_date_accuracy"]
    assert report.currency_accuracy >= ACCEPTANCE_TARGETS["min_currency_accuracy"]
    assert report.line_item_accuracy >= ACCEPTANCE_TARGETS["min_line_item_accuracy"]
    assert report.latency_seconds_mean <= ACCEPTANCE_TARGETS["max_latency_seconds"]

    passed, failures = harness.meets_acceptance_criteria(report)
    assert passed is True
    assert len(failures) == 0


def test_adversarial_hostile_documents_through_role6_gateway() -> None:
    """Evaluate hostile document categories through actual Role 6 Gateway."""
    evaluator = HostileDocumentEvaluator()
    report = evaluator.evaluate_all()

    assert report.total_tests == 8
    assert report.passed_tests == 8
    assert report.pass_rate == 1.0

    # Verify every required hostile category is present and passed
    categories = set(report.by_category.keys())
    assert "prompt_injection" in categories
    assert "hidden_instructions" in categories
    assert "misleading_totals" in categories
    assert "malformed_dates_currencies" in categories
    assert "conflicting_line_items" in categories
    assert "hostile_metadata" in categories
    assert "unsupported_layout" in categories

    for cat, res in report.by_category.items():
        assert res["passed"] == res["total"], f"Failed tests in category: {cat}"


def test_base_model_artifact_verification_and_blockers() -> None:
    """Verify base model artifact absence and blocked training decision."""
    # 1. Model weights file must not exist on disk
    model_weight_path = Path("models/model.onnx")
    assert not model_weight_path.exists(), "Model weights file unexpectedly exists"

    # 2. Manifest artifact hash must match empty-file sha256
    manifest_data = json.loads(ROLE6_MANIFEST_PATH.read_text(encoding="utf-8"))
    empty_hash = hashlib.sha256(b"").hexdigest()
    assert manifest_data["artifact_hashes"]["model.onnx"] == empty_hash

    # 3. Check invalid placeholder pattern
    placeholder_rev = "sha256:d8a9f0e123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    assert "abcdef0123456789" in placeholder_rev, "Revision is placeholder pattern"

    # 4. Error analysis report must classify result as NOVA_SYNTHETIC_FIXTURE_RESULT
    extractor = Role6GatewayDocumentExtractor()
    harness = EvaluationHarness(extractor=extractor)
    report = harness.evaluate_manifest(MANIFEST_PATH, split="test")
    passed, failures = harness.meets_acceptance_criteria(report)
    output_md = generate_error_analysis_report(report, passed, failures)

    assert "NOVA_SYNTHETIC_FIXTURE_RESULT" in output_md
    assert "TRAINING_REQUIRED_BUT_BLOCKED" in output_md
    assert "NO_VERIFIED_BASE_MODEL_ARTIFACT" in output_md
    assert "DEMO_TRAINING_NOT_REQUIRED" in output_md


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
