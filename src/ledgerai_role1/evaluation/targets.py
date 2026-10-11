"""Pre-declared acceptance criteria targets for Role 1 Document Intelligence."""

from __future__ import annotations

from typing import Final

# Acceptance criteria established before training/tuning decisions
ACCEPTANCE_TARGETS: Final[dict[str, float]] = {
    "min_f1": 0.95,
    "min_exact_match": 0.90,
    "min_normalized_match": 0.95,
    "min_date_accuracy": 0.95,
    "min_currency_accuracy": 0.98,
    "min_decimal_amount_exact_match": 0.95,
    "min_line_item_accuracy": 0.90,
    "max_invalid_schema_rate": 0.00,  # Strict zero-tolerance for schema violations
    "max_hallucination_rate": 0.02,
    "max_cer": 0.05,
    "max_latency_seconds": 1.00,
}
