"""Versioned, bounded strategy configuration."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrategyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_version: str
    algorithm_version: str
    rule_version: str
    supported_currencies: frozenset[str]
    date_window_days: int = Field(ge=0, le=31)
    amount_tolerance: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    ambiguity_delta: Decimal = Field(ge=Decimal("0"), le=Decimal("0.25"))
    minimum_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    maximum_invoices: int = Field(ge=1, le=1000)
    maximum_transactions: int = Field(ge=1, le=1000)
    maximum_candidates_per_record: int = Field(ge=1, le=200)
    maximum_candidate_edges: int = Field(ge=1, le=100_000)
    maximum_group_size: int = Field(ge=2, le=8)
    maximum_group_combinations: int = Field(ge=1, le=100_000)
    weights: dict[str, Decimal]

    @model_validator(mode="after")
    def validate_weights(self) -> Self:
        expected = {"reference", "amount", "date", "party", "evidence"}
        if set(self.weights) != expected or sum(self.weights.values()) != Decimal("1"):
            raise ValueError("strategy weights must contain the five components and sum to one")
        if any(value < 0 or value > 1 for value in self.weights.values()):
            raise ValueError("strategy weights must be between zero and one")
        return self


def load_strategy(path: Path | None = None) -> StrategyConfig:
    if path is None:
        path = Path(__file__).resolve().parents[3] / "config" / "reconciliation-strategies.v1.json"
    return StrategyConfig.model_validate_json(path.read_text(encoding="utf-8"))
