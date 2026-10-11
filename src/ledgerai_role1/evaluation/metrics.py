"""Deterministic evaluation metrics for financial document extraction."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field


def normalize_text(text: str | None) -> str:
    """Normalize text for invariant comparison (lowercase, trimmed whitespace, collapsed spaces)."""
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def character_error_rate(reference: str, hypothesis: str) -> float:
    """Calculate character error rate (CER) using Levenshtein distance."""
    ref = list(reference)
    hyp = list(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    matcher = difflib.SequenceMatcher(None, ref, hyp)
    distance = sum(
        max(tag_len_ref, tag_len_hyp)
        for tag, alo, ahi, blo, bhi in matcher.get_opcodes()
        if tag != "equal"
        for tag_len_ref, tag_len_hyp in [(ahi - alo, bhi - blo)]
    )
    return min(1.0, distance / len(ref))


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Calculate word error rate (WER)."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    matcher = difflib.SequenceMatcher(None, ref_words, hyp_words)
    distance = sum(
        max(ahi - alo, bhi - blo)
        for tag, alo, ahi, blo, bhi in matcher.get_opcodes()
        if tag != "equal"
    )
    return min(1.0, distance / len(ref_words))


@dataclass
class FieldEvaluationResult:
    total_samples: int = 0
    exact_matches: int = 0
    normalized_matches: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    cer_sum: float = 0.0
    wer_sum: float = 0.0
    hallucinated_count: int = 0

    @property
    def exact_match_rate(self) -> float:
        return self.exact_matches / self.total_samples if self.total_samples else 1.0

    @property
    def normalized_match_rate(self) -> float:
        return self.normalized_matches / self.total_samples if self.total_samples else 1.0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 1.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r) / (p + r) if (p + r) > 0 else 0.0

    @property
    def average_cer(self) -> float:
        return self.cer_sum / self.total_samples if self.total_samples else 0.0

    @property
    def average_wer(self) -> float:
        return self.wer_sum / self.total_samples if self.total_samples else 0.0

    @property
    def hallucination_rate(self) -> float:
        return self.hallucinated_count / self.total_samples if self.total_samples else 0.0


@dataclass
class EvaluationAggregateReport:
    """Aggregate report across all fields and document types."""

    total_documents: int = 0
    total_valid_schema: int = 0
    unsupported_abstentions: int = 0
    date_accuracy: float = 0.0
    currency_accuracy: float = 0.0
    decimal_amount_exact_match: float = 0.0
    line_item_accuracy: float = 0.0
    calibration_error: float = 0.0
    latency_seconds_mean: float = 0.0
    memory_peak_mb: float = 0.0
    field_metrics: dict[str, FieldEvaluationResult] = field(default_factory=dict)
    by_document_type: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def invalid_schema_rate(self) -> float:
        if not self.total_documents:
            return 0.0
        return (self.total_documents - self.total_valid_schema) / self.total_documents

    @property
    def abstention_rate(self) -> float:
        if not self.total_documents:
            return 0.0
        return self.unsupported_abstentions / self.total_documents
