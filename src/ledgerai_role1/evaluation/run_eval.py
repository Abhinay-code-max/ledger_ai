"""Run evaluation harness and generate error analysis report."""

from __future__ import annotations

from pathlib import Path

from ledgerai_role1.evaluation.error_analysis import generate_error_analysis_report
from ledgerai_role1.evaluation.harness import EvaluationHarness


def main() -> None:
    manifest_path = Path("data/manifests/nova_dataset_manifest.json")
    harness = EvaluationHarness()
    report = harness.evaluate_manifest(manifest_path, split="test")
    passed, failures = harness.meets_acceptance_criteria(report)

    output_md = generate_error_analysis_report(report, passed, failures)
    doc_path = Path("docs/error_analysis_report.md")
    doc_path.write_text(output_md, encoding="utf-8")
    print(
        f"Evaluation completed. Passed acceptance criteria: {passed}. Report written to {doc_path}"
    )


if __name__ == "__main__":
    main()
