"""Run evaluation harness across synthetic fixtures, unseen documents, and hostile tests."""

from __future__ import annotations

from pathlib import Path

from ledgerai_role1.evaluation.error_analysis import generate_error_analysis_report
from ledgerai_role1.evaluation.harness import EvaluationHarness
from ledgerai_role1.evaluation.hostile_evaluation import HostileDocumentEvaluator
from ledgerai_role1.pipeline.adapters import Role6GatewayDocumentExtractor


def main() -> None:
    synth_manifest_path = Path("data/manifests/nova_dataset_manifest.json")
    unseen_manifest_path = Path("data/manifests/unseen_evaluation_manifest.json")

    extractor = Role6GatewayDocumentExtractor()
    harness = EvaluationHarness(extractor=extractor)

    # 1. Evaluate synthetic demo fixtures (N=5)
    synth_report = harness.evaluate_manifest(synth_manifest_path, split="test")
    passed_targets, failures = harness.meets_acceptance_criteria(synth_report)

    # 2. Evaluate representative unseen documents (N=10)
    unseen_report = None
    if unseen_manifest_path.exists():
        unseen_report = harness.evaluate_manifest(unseen_manifest_path, split="test")

    # 3. Evaluate adversarial hostile documents through Role 6 gateway
    hostile_evaluator = HostileDocumentEvaluator(extractor=extractor)
    hostile_report = hostile_evaluator.evaluate_all()

    # 4. Generate structured error analysis and model readiness report
    output_md = generate_error_analysis_report(
        synthetic_report=synth_report,
        unseen_report=unseen_report,
        hostile_report=hostile_report,
        passed_targets=passed_targets,
        failure_reasons=failures,
    )

    doc_path = Path("docs/error_analysis_report.md")
    doc_path.write_text(output_md, encoding="utf-8")
    unseen_count = unseen_report.total_documents if unseen_report else 0
    unseen_acc = f"{unseen_report.decimal_amount_exact_match:.1%}" if unseen_report else "N/A"
    print(
        f"Evaluation completed successfully.\n"
        f"  Synthetic fixtures evaluated: {synth_report.total_documents} "
        f"(Amount match: {synth_report.decimal_amount_exact_match:.1%})\n"
        f"  Unseen documents evaluated:   {unseen_count} "
        f"(Amount match: {unseen_acc})\n"
        f"  Hostile tests passed:         "
        f"{hostile_report.passed_tests}/{hostile_report.total_tests}\n"
        f"  Report written to:            {doc_path}"
    )


if __name__ == "__main__":
    main()
