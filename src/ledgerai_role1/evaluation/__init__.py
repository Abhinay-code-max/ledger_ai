"""Evaluation harness, metrics, and error analysis for Role 1."""

from ledgerai_role1.evaluation.error_analysis import generate_error_analysis_report
from ledgerai_role1.evaluation.harness import EvaluationHarness
from ledgerai_role1.evaluation.metrics import (
    EvaluationAggregateReport,
    FieldEvaluationResult,
    character_error_rate,
    normalize_text,
    word_error_rate,
)
from ledgerai_role1.evaluation.targets import ACCEPTANCE_TARGETS

__all__ = [
    "ACCEPTANCE_TARGETS",
    "EvaluationAggregateReport",
    "EvaluationHarness",
    "FieldEvaluationResult",
    "character_error_rate",
    "generate_error_analysis_report",
    "normalize_text",
    "word_error_rate",
]
