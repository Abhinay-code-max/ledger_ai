"""Run evaluation harness through Role 6 gateway and generate error analysis report."""

from __future__ import annotations

from pathlib import Path

from ledgerai_role1.evaluation.error_analysis import generate_error_analysis_report
from ledgerai_role1.evaluation.harness import EvaluationHarness
from ledgerai_role1.evaluation.hostile_evaluation import HostileDocumentEvaluator
from ledgerai_role1.pipeline.adapters import Role6GatewayDocumentExtractor


def main() -> None:
    manifest_path = Path("data/manifests/nova_dataset_manifest.json")
    extractor = Role6GatewayDocumentExtractor()
    harness = EvaluationHarness(extractor=extractor)
    report = harness.evaluate_manifest(manifest_path, split="test")
    passed, failures = harness.meets_acceptance_criteria(report)

    # Evaluate hostile documents through Role 6 gateway
    hostile_evaluator = HostileDocumentEvaluator(extractor=extractor)
    hostile_report = hostile_evaluator.evaluate_all()

    output_md = generate_error_analysis_report(
        report, passed, failures, hostile_report=hostile_report
    )
    doc_path = Path("docs/error_analysis_report.md")
    doc_path.write_text(output_md, encoding="utf-8")
    print(
        f"Evaluation through Role 6 gateway completed. Passed acceptance criteria: {passed}. "
        f"Hostile tests pass rate: {hostile_report.pass_rate:.1%}. Report written to {doc_path}"
    )


if __name__ == "__main__":
    main()
