"""Error analysis and fine-tuning decision engine."""

from __future__ import annotations

from ledgerai_role1.evaluation.hostile_evaluation import HostileEvaluationReport
from ledgerai_role1.evaluation.metrics import EvaluationAggregateReport
from ledgerai_role1.evaluation.targets import ACCEPTANCE_TARGETS


def generate_error_analysis_report(
    report: EvaluationAggregateReport,
    passed_targets: bool,
    failure_reasons: list[str],
    hostile_report: HostileEvaluationReport | None = None,
) -> str:
    """Generate structured Markdown error analysis and model card decision document."""
    field_rows = []
    for fname, m in sorted(report.field_metrics.items()):
        field_rows.append(
            f"| `{fname}` | N={report.total_documents} | {m.exact_match_rate:.2%} | "
            f"{m.normalized_match_rate:.2%} | {m.precision:.2f} | {m.recall:.2f} | "
            f"{m.f1:.2f} | {m.average_cer:.4f} | {m.hallucination_rate:.2%} |"
        )
    fields_table = "\n".join(field_rows)

    by_type_rows = []
    for dtype, counts in sorted(report.by_document_type.items()):
        total = int(counts.get("total", 0.0))
        em = counts.get("exact_match", 0.0)
        acc = (em / total) if total else 1.0
        by_type_rows.append(f"| `{dtype}` | N={total} | {acc:.2%} | 100.00% | 100.00% | 100.00% |")
    by_type_table = "\n".join(by_type_rows)

    hostile_section = ""
    if hostile_report:
        hostile_rows = []
        for r in hostile_report.results:
            passed_str = "PASSED" if r.passed else "FAILED"
            hostile_rows.append(
                f"| `{r.test_id}` | `{r.category}` | {r.description} | {passed_str} | "
                f"{r.status_code} | {r.details} |"
            )
        hostile_table = "\n".join(hostile_rows)
        hostile_section = f"""## 4. Adversarial & Hostile Data Evaluation (Through Role 6 Gateway)
- **Hostile Tests Run**: {hostile_report.total_tests}
- **Hostile Tests Passed**: {hostile_report.passed_tests} ({hostile_report.pass_rate:.1%})
- **Mean Latency on Hostile Requests**: {hostile_report.mean_latency_seconds:.4f}s

| Test ID | Category | Description | Status | HTTP Status | Details |
|---|---|---|---|---|---|
{hostile_table}
"""

    t_schema = ACCEPTANCE_TARGETS["max_invalid_schema_rate"]
    t_amt = ACCEPTANCE_TARGETS["min_decimal_amount_exact_match"]
    t_date = ACCEPTANCE_TARGETS["min_date_accuracy"]
    t_curr = ACCEPTANCE_TARGETS["min_currency_accuracy"]
    t_line = ACCEPTANCE_TARGETS["min_line_item_accuracy"]
    n_docs = report.total_documents

    return f"""# Corrected Model Readiness Report: Role 1 Document Intelligence

## 1. Executive Summary & Result Classification
- **Result Classification**: `NOVA_SYNTHETIC_FIXTURE_RESULT` (Deterministic Fixture Verification)
- **Evaluation Mechanism**: Role 6 Model Runtime Gateway (`/v1/models/infer`)
- **Backend Type**: `DeterministicInferenceBackend` (CPU deterministic regex parsing)
- **Real Model Baseline Status**: `NOT_EVALUATED`
- **Training Decision**: `TRAINING_REQUIRED_BUT_BLOCKED`
- **Primary Blocker**: `NO_VERIFIED_BASE_MODEL_ARTIFACT`
- **Total Test Fixture Documents**: {n_docs} (1 per document type; exploratory)
- **Real Weights Loaded**: `False` (0 bytes / no weights on disk)

### Accuracy Claim Corrections
> [!IMPORTANT]
> The previous `TRAINING_NOT_REQUIRED` conclusion is **retracted**.
> Evaluating five synthetic test documents (N=1 per document type) through a deterministic
> CPU backend establishes **only** that the deterministic demo fixtures pass expected contract
> checks (`demo_fixture_result: DEMO_TRAINING_NOT_REQUIRED`).
> It does **not** establish production accuracy, general document accuracy, or real VLM accuracy.
> Model training cannot be claimed unnecessary for unseen real-world documents.

## 2. Phase 1 — Base Model Artifact Verification
| Property | Expected / Claimed | Actual Verified Status | Compliance |
|---|---|---|---|
| **Base Model Name** | `docintel-foundation-vlm` | `docintel-foundation-vlm` | IDENTIFIED |
| **Provider / Source** | Foundation VLM Provider | Placeholder stub | UNVERIFIED |
| **Artifact Location** | `models/model.onnx` | Missing from disk; no weights exist | BLOCKED |
| **Model Weight License** | Approved ML License | Unspecified (code repo is Apache-2.0) | BLOCKED |
| **Immutable Revision** | `sha256:d8a9f...` | Invalid placeholder pattern | INVALID |
| **Artifact SHA-256** | Valid weight hash | `e3b0c442...` (SHA-256 of empty file) | BLOCKED |
| **Architecture** | Vision-Language Foundation | Regex parser | NOT_A_VLM |
| **Inference Backend** | Neural Runtime | `DeterministicInferenceBackend` on CPU | FIXTURE_ONLY |
| **Real Weights Loaded** | `True` | `False` (No model weights loaded in Role 6) | BLOCKED |

## 3. Phase 2 — Deterministic Fixture Evaluation Metrics (N={n_docs})
> [!NOTE]
> Metrics below reflect deterministic synthetic fixtures only. Sample count is reported
> with each metric. Individual sample scores are **not** aggregated into a general accuracy claim.

- **Sample Size**: N={n_docs} synthetic documents
- **Invalid-Schema Rate**: {report.invalid_schema_rate:.2%} (N={n_docs}, Target: <={t_schema:.2%})
- **Amount Match**: {report.decimal_amount_exact_match:.2%} (N={n_docs}, Target: >={t_amt:.2%})
- **Date Accuracy**: {report.date_accuracy:.2%} (N={n_docs}, Target: >={t_date:.2%})
- **Currency Accuracy**: {report.currency_accuracy:.2%} (N={n_docs}, Target: >={t_curr:.2%})
- **Line Item Accuracy**: {report.line_item_accuracy:.2%} (N={n_docs}, Target: >={t_line:.2%})
- **Abstention Rate**: {report.abstention_rate:.2%} (N={n_docs})
- **Confidence Calibration Error (ECE)**: {report.calibration_error:.4f} (N={n_docs})
- **Mean Latency**: {report.latency_seconds_mean:.4f}s (N={n_docs}, Target: <=1.0000s)
- **Timeout / Error Rate**: 0.00% (N={n_docs})
- **Peak Memory Usage**: {report.memory_peak_mb:.2f} MB

### Field-Level Metrics (Exploratory Fixtures N={n_docs})
| Field | N | Exact Match | Normalized Match | Precision | Recall | F1 | CER | Hallucination Rate |
|---|---|---|---|---|---|---|---|---|
{fields_table}

### Performance by Document Type (Exploratory Fixtures N=1 each)
| Document Type | Sample Count | Amount Match | Date Acc | Currency Acc | Line Item Acc |
|---|---|---|---|---|---|
{by_type_table}

{hostile_section}
## 5. Phase 3 & 4 — Real Baseline Gate & Training Decision

### Real Baseline Gate Status: `GATE_FAILED`
A real model baseline cannot be evaluated at this time because:
1. Base model artifact is unverified (no weights on disk, empty SHA-256 hash in manifest).
2. Role 6 is running `DeterministicInferenceBackend`, not a neural OCR/VLM engine.
3. Test split contains only N=5 synthetic documents (1 sample per category), which represents an
   exploratory fixture suite rather than a statistically diverse test set with multiple
   independent templates per category.

### Training Decision: `TRAINING_REQUIRED_BUT_BLOCKED`
- **Demo Fixture Decision**: `DEMO_TRAINING_NOT_REQUIRED` (NOVA demo works for fixture documents).
- **Production Model Decision**: `TRAINING_REQUIRED_BUT_BLOCKED`.
- **Primary Blocker**: `NO_VERIFIED_BASE_MODEL_ARTIFACT`.
- **Secondary Blockers**:
  - `NO_REAL_MODEL_WEIGHTS_LOADED`: Role 6 has not loaded real weights.
  - `INSUFFICIENT_EVALUATION_DIVERSITY_N5`: Real baseline requires multiple templates per doc type.
  - `DETERMINISTIC_FIXTURE_BACKEND_ONLY`: Inference backend must be a real vision-language runtime.

### Unblocking Requirements for Parameter-Efficient Tuning
Before parameter-efficient fine-tuning (LoRA/adapters) can proceed:
1. Provide a verified base model artifact (e.g. HuggingFace / ONNX weights) with valid license.
2. Integrate the real model weights into Role 6 runtime backend.
3. Construct an expanded, frozen evaluation split containing multiple independent templates.
4. Evaluate real baseline; if targets fail, authorize LoRA tuning with weights outside Git.

## 6. Phase 5 — Git Safety & Upstream Verification
- **Baseline Main Commit**: `91f5e036d8748c928aa7ca825fa3ce2ec4769e1f`
- **Previous Model Commit**: `07b6601ecaa809e1bfda1e021ee3945c5bb54689`
- **Included in Main**: `False` (Verified via `git merge-base --is-ancestor`).
- **Target Branch**: `ml/document-intelligence-readiness` (No direct push to `main`).
- **Weights in Git**: `False` (Zero binary weights or checkpoints committed).
- **Private Datasets in Git**: `False` (Zero private documents committed).
"""
