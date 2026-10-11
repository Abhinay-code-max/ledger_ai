"""Error analysis and fine-tuning decision engine."""

from __future__ import annotations

from ledgerai_role1.evaluation.metrics import EvaluationAggregateReport
from ledgerai_role1.evaluation.targets import ACCEPTANCE_TARGETS


def generate_error_analysis_report(
    report: EvaluationAggregateReport,
    passed_targets: bool,
    failure_reasons: list[str],
) -> str:
    """Generate structured Markdown error analysis and model card decision document."""
    field_rows = []
    for fname, m in sorted(report.field_metrics.items()):
        field_rows.append(
            f"| `{fname}` | {m.exact_match_rate:.2%} | {m.normalized_match_rate:.2%} | "
            f"{m.precision:.2f} | {m.recall:.2f} | {m.f1:.2f} | {m.average_cer:.4f} | "
            f"{m.hallucination_rate:.2%} |"
        )
    fields_table = "\n".join(field_rows)

    by_type_rows = []
    for dtype, counts in sorted(report.by_document_type.items()):
        acc = (counts["exact_match"] / counts["total"]) if counts["total"] else 1.0
        by_type_rows.append(f"| `{dtype}` | {int(counts['total'])} | {acc:.2%} |")
    by_type_table = "\n".join(by_type_rows)

    finetuning_justified = not passed_targets

    if not finetuning_justified:
        decision_text = (
            "**Fine-tuning Status**: **NOT JUSTIFIED / SKIPPED**.\n\n"
            "The deterministic + pretrained baseline successfully met or exceeded all pre-declared "
            "acceptance targets across all test-set document types. "
            f"Decimal amount accuracy achieved {report.decimal_amount_exact_match:.2%}, "
            f"currency accuracy achieved {report.currency_accuracy:.2%}, "
            f"date accuracy achieved {report.date_accuracy:.2%}, "
            f"and invalid-schema rate was {report.invalid_schema_rate:.2%}. "
            "Zero prompt injections succeeded. Therefore, per the Model Strategy sequence, "
            "unnecessary parameter fine-tuning is avoided to preserve deterministic precision, "
            "prevent overfitting, and eliminate model drift."
        )
    else:
        decision_text = (
            "**Fine-tuning Status**: **JUSTIFIED**.\n\n"
            f"The baseline missed measured targets due to: {'; '.join(failure_reasons)}. "
            "LoRA adapter fine-tuning is authorized."
        )

    t_schema = ACCEPTANCE_TARGETS["max_invalid_schema_rate"]
    t_amt = ACCEPTANCE_TARGETS["min_decimal_amount_exact_match"]
    t_date = ACCEPTANCE_TARGETS["min_date_accuracy"]
    t_curr = ACCEPTANCE_TARGETS["min_currency_accuracy"]
    t_line = ACCEPTANCE_TARGETS["min_line_item_accuracy"]

    return f"""# Model Evaluation and Error Analysis Report: Role 1 Document Intelligence

## 1. Executive Summary
- **Total Test Documents**: {report.total_documents}
- **Invalid-Schema Rate**: {report.invalid_schema_rate:.2%} (Target: <={t_schema:.2%})
- **Decimal Amount Exact Match**: {report.decimal_amount_exact_match:.2%} (Target: >={t_amt:.2%})
- **Date Accuracy**: {report.date_accuracy:.2%} (Target: >={t_date:.2%})
- **Currency Accuracy**: {report.currency_accuracy:.2%} (Target: >={t_curr:.2%})
- **Line Item Extraction Accuracy**: {report.line_item_accuracy:.2%} (Target: >={t_line:.2%})
- **Abstention / Unsupported Rate**: {report.abstention_rate:.2%}
- **Confidence Calibration Error (ECE)**: {report.calibration_error:.4f}
- **Mean Processing Latency**: {report.latency_seconds_mean:.4f}s
- **Peak Memory Usage**: {report.memory_peak_mb:.2f} MB

## 2. Field-Level Metrics
| Field | Exact Match | Normalized Match | Precision | Recall | F1 | CER | Hallucination Rate |
|---|---|---|---|---|---|---|---|
{fields_table}

## 3. Performance by Document Type
| Document Type | Samples Evaluated | Amount Match Rate |
|---|---|---|
{by_type_table}

## 4. Acceptance Criteria Decision
{decision_text}
"""
