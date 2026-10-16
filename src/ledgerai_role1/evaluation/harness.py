"""Deterministic evaluation harness for document intelligence benchmarking."""

from __future__ import annotations

import json
import time
import tracemalloc
from decimal import Decimal
from pathlib import Path

from ledgerai_role1.evaluation.metrics import (
    EvaluationAggregateReport,
    FieldEvaluationResult,
    character_error_rate,
    normalize_text,
    word_error_rate,
)
from ledgerai_role1.evaluation.targets import ACCEPTANCE_TARGETS
from ledgerai_role1.governance.manifest import DatasetManifest
from ledgerai_role1.ontology.schema import CanonicalDocumentData
from ledgerai_role1.pipeline.adapters import ModelGatewayAdapter
from ledgerai_role1.pipeline.pretrained_baseline import PretrainedDocumentExtractor


class EvaluationHarness:
    """Runs deterministic evaluation across split samples and compiles audit metrics."""

    def __init__(
        self,
        extractor: ModelGatewayAdapter | PretrainedDocumentExtractor | None = None,
    ) -> None:
        self.extractor = extractor or PretrainedDocumentExtractor()

    def evaluate_manifest(
        self,
        manifest_path: Path,
        *,
        split: str = "test",
        root_dir: Path | None = None,
    ) -> EvaluationAggregateReport:
        manifest = DatasetManifest.load_from_file(manifest_path)
        base_dir = root_dir or manifest_path.parent.parent.parent

        samples = [s for s in manifest.samples if s.split == split]
        if not samples:
            raise ValueError(f"No samples found for split '{split}' in manifest")

        report = EvaluationAggregateReport(total_documents=len(samples))
        field_names = [
            "document_number",
            "supplier_name",
            "customer_name",
            "issue_date",
            "due_date",
            "subtotal",
            "tax_amount",
            "total_amount",
            "currency",
            "bank_account_reference",
        ]
        for fn in field_names:
            report.field_metrics[fn] = FieldEvaluationResult()

        latencies: list[float] = []
        date_correct = 0
        date_total = 0
        currency_correct = 0
        total_amount_exact = 0
        line_item_matches = 0
        line_item_totals = 0
        calibration_diffs: list[float] = []

        tracemalloc.start()

        for sample in samples:
            doc_file = base_dir / Path(str(sample.document_path).replace("\\", "/"))
            gt_file = base_dir / Path(str(sample.ground_truth_path).replace("\\", "/"))

            if not doc_file.exists() or not gt_file.exists():
                raise FileNotFoundError(f"Missing sample file: {doc_file} or {gt_file}")

            doc_bytes = doc_file.read_bytes()
            gt_data = CanonicalDocumentData.model_validate(
                json.loads(gt_file.read_text(encoding="utf-8"))
            )

            # Run extractor with latency measurement
            start_time = time.perf_counter()
            try:
                extracted = self.extractor.extract(doc_bytes, media_type=sample.media_type)
                report.total_valid_schema += 1
            except Exception:
                extracted = None
            duration = time.perf_counter() - start_time
            latencies.append(duration)

            if extracted is None:
                continue

            # Check abstention
            if extracted.document_type.value == "UNKNOWN":
                report.unsupported_abstentions += 1

            # Document-type tracking
            doc_type_key = sample.document_type.value
            if doc_type_key not in report.by_document_type:
                report.by_document_type[doc_type_key] = {"total": 0.0, "exact_match": 0.0}
            report.by_document_type[doc_type_key]["total"] += 1.0

            # Evaluate each field
            for fn in field_names:
                metric = report.field_metrics[fn]
                metric.total_samples += 1

                gt_val = getattr(gt_data, fn, None)
                pred_val = getattr(extracted, fn, None)

                # Ground truth string representation
                gt_str = str(gt_val) if gt_val is not None else ""
                pred_str = str(pred_val) if pred_val is not None else ""

                if gt_val is None and pred_val is not None:
                    metric.hallucinated_count += 1
                    metric.false_positives += 1
                elif gt_val is not None and pred_val is None:
                    metric.false_negatives += 1
                elif gt_val is not None and pred_val is not None:
                    metric.true_positives += 1

                    # Exact match
                    if gt_str == pred_str:
                        metric.exact_matches += 1

                    # Normalized match
                    if normalize_text(gt_str) == normalize_text(pred_str):
                        metric.normalized_matches += 1

                    # CER / WER
                    metric.cer_sum += character_error_rate(gt_str, pred_str)
                    metric.wer_sum += word_error_rate(gt_str, pred_str)

                    # Calibration tracking (confidence vs match)
                    conf = float(extracted.confidences.get(fn, Decimal("0.95")))
                    is_correct = 1.0 if gt_str == pred_str else 0.0
                    calibration_diffs.append(abs(conf - is_correct))
                else:
                    # Both None
                    metric.exact_matches += 1
                    metric.normalized_matches += 1

            # Specific evaluation categories
            # Date accuracy
            if gt_data.issue_date:
                date_total += 1
                if extracted.issue_date == gt_data.issue_date:
                    date_correct += 1

            # Currency accuracy
            if extracted.currency == gt_data.currency:
                currency_correct += 1

            # Decimal amount exact match
            if extracted.total_amount == gt_data.total_amount:
                total_amount_exact += 1
                report.by_document_type[doc_type_key]["exact_match"] += 1.0

            # Line item accuracy
            if len(gt_data.line_items) == len(extracted.line_items):
                matched = True
                for g_item, p_item in zip(gt_data.line_items, extracted.line_items, strict=False):
                    if (
                        normalize_text(g_item.description) != normalize_text(p_item.description)
                        or g_item.line_amount != p_item.line_amount
                    ):
                        matched = False
                        break
                if matched:
                    line_item_matches += 1
            line_item_totals += 1

        peak_mem = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
        tracemalloc.stop()

        report.latency_seconds_mean = sum(latencies) / len(latencies) if latencies else 0.0
        report.memory_peak_mb = peak_mem
        report.date_accuracy = date_correct / date_total if date_total else 1.0
        report.currency_accuracy = currency_correct / len(samples) if samples else 1.0
        report.decimal_amount_exact_match = total_amount_exact / len(samples) if samples else 1.0
        report.line_item_accuracy = (
            line_item_matches / line_item_totals if line_item_totals else 1.0
        )
        report.calibration_error = (
            sum(calibration_diffs) / len(calibration_diffs) if calibration_diffs else 0.0
        )

        return report

    def meets_acceptance_criteria(
        self, report: EvaluationAggregateReport
    ) -> tuple[bool, list[str]]:
        """Verify whether measured metrics fulfill pre-declared acceptance targets."""
        failures: list[str] = []

        if report.invalid_schema_rate > ACCEPTANCE_TARGETS["max_invalid_schema_rate"]:
            failures.append(
                f"invalid_schema_rate {report.invalid_schema_rate:.4f} > "
                f"target {ACCEPTANCE_TARGETS['max_invalid_schema_rate']:.4f}"
            )
        if report.decimal_amount_exact_match < ACCEPTANCE_TARGETS["min_decimal_amount_exact_match"]:
            failures.append(
                f"decimal_amount_exact_match {report.decimal_amount_exact_match:.4f} < "
                f"target {ACCEPTANCE_TARGETS['min_decimal_amount_exact_match']:.4f}"
            )
        if report.date_accuracy < ACCEPTANCE_TARGETS["min_date_accuracy"]:
            failures.append(
                f"date_accuracy {report.date_accuracy:.4f} < "
                f"target {ACCEPTANCE_TARGETS['min_date_accuracy']:.4f}"
            )
        if report.currency_accuracy < ACCEPTANCE_TARGETS["min_currency_accuracy"]:
            failures.append(
                f"currency_accuracy {report.currency_accuracy:.4f} < "
                f"target {ACCEPTANCE_TARGETS['min_currency_accuracy']:.4f}"
            )
        if report.line_item_accuracy < ACCEPTANCE_TARGETS["min_line_item_accuracy"]:
            failures.append(
                f"line_item_accuracy {report.line_item_accuracy:.4f} < "
                f"target {ACCEPTANCE_TARGETS['min_line_item_accuracy']:.4f}"
            )

        # Average F1 across all fields
        f1_scores = [m.f1 for m in report.field_metrics.values()]
        avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
        if avg_f1 < ACCEPTANCE_TARGETS["min_f1"]:
            failures.append(f"mean_f1 {avg_f1:.4f} < target {ACCEPTANCE_TARGETS['min_f1']:.4f}")

        # Hallucination rate
        hallucination_rates = [m.hallucination_rate for m in report.field_metrics.values()]
        max_hal = max(hallucination_rates) if hallucination_rates else 0.0
        if max_hal > ACCEPTANCE_TARGETS["max_hallucination_rate"]:
            failures.append(
                f"max_hallucination_rate {max_hal:.4f} > "
                f"target {ACCEPTANCE_TARGETS['max_hallucination_rate']:.4f}"
            )

        return len(failures) == 0, failures
