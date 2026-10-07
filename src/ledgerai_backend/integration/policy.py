"""Small, deterministic, code-free policy evaluator.

The evaluator deliberately supports only a closed set of fields and operators. It never
interprets strings as Python, SQL, templates, regular expressions, or paths.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator

PolicyOutcome = Literal["AUTO_ELIGIBLE", "REVIEW_REQUIRED", "ESCALATED", "BLOCKED"]
Operator = Literal["eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in", "exists"]
Scalar: TypeAlias = str | bool | int | Decimal | date | datetime | None

ALLOWED_FIELDS = frozenset(
    {
        "extraction_confidence",
        "reconciliation_confidence",
        "amount",
        "currency",
        "risk_category",
        "exception_severity",
        "missing_evidence",
        "document_category",
        "transaction_category",
        "legal_entity_id",
        "maker_checker_required",
    }
)
MAX_RULES = 500
MAX_CONDITIONS = 32


class PolicyCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    operator: Operator
    operand: Scalar | list[str | bool | int | Decimal] = None

    @field_validator("operand", mode="before")
    @classmethod
    def reject_floats(cls, value: object) -> object:
        values = value if isinstance(value, list) else [value]
        if any(isinstance(item, float) for item in values):
            raise ValueError("numeric policy values must use exact decimals")
        return value

    @field_validator("field")
    @classmethod
    def allow_field(cls, value: str) -> str:
        if value not in ALLOWED_FIELDS:
            raise ValueError("policy field is not allowlisted")
        return value


class PolicyRuleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,99}$")
    priority: int = Field(ge=0, le=1_000_000)
    conditions: list[PolicyCondition] = Field(min_length=1, max_length=MAX_CONDITIONS)
    outcome: PolicyOutcome
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,99}$")
    explanation: str = Field(min_length=1, max_length=500)


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    outcome: PolicyOutcome
    matched_rule_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    explanation: str


_OUTCOME_PRECEDENCE: dict[str, int] = {
    "AUTO_ELIGIBLE": 0,
    "REVIEW_REQUIRED": 1,
    "ESCALATED": 2,
    "BLOCKED": 3,
}


def _decimal(value: object) -> Decimal:
    if isinstance(value, (bool, float)):
        raise ValueError("numeric policy values must use exact decimals")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid numeric policy value") from exc


def _compare(actual: Scalar, condition: PolicyCondition) -> bool:
    operator = condition.operator
    operand = condition.operand
    if operator == "exists":
        if not isinstance(operand, bool):
            raise ValueError("exists requires a boolean operand")
        return (actual is not None) is operand
    if operator in {"in", "not_in"}:
        if not isinstance(operand, list) or not operand:
            raise ValueError(f"{operator} requires a non-empty list operand")
        result = actual in operand
        return result if operator == "in" else not result
    if isinstance(operand, list) or operand is None or actual is None:
        raise ValueError(f"{operator} requires scalar values")
    if operator == "eq":
        return actual == operand
    if operator == "ne":
        return actual != operand
    if isinstance(actual, Decimal) or isinstance(operand, Decimal):
        left: Any = _decimal(actual)
        right: Any = _decimal(operand)
    else:
        if type(actual) is not type(operand):
            raise ValueError("ordered policy operands must have the same type")
        left, right = actual, operand
    if operator == "lt":
        return bool(left < right)
    if operator == "lte":
        return bool(left <= right)
    if operator == "gt":
        return bool(left > right)
    if operator == "gte":
        return bool(left >= right)
    raise ValueError("unsupported policy operator")


def evaluate_policy(
    inputs: dict[str, Scalar],
    rules: Sequence[PolicyRuleSpec | dict[str, object]],
    *,
    default_outcome: PolicyOutcome = "REVIEW_REQUIRED",
) -> PolicyEvaluation:
    """Evaluate rules reproducibly; same-priority conflicts resolve to safer outcome.

    Only rules at the highest matching priority contribute. Within that priority, the
    strictest result wins using BLOCKED > ESCALATED > REVIEW_REQUIRED > AUTO_ELIGIBLE.
    """
    unknown = set(inputs).difference(ALLOWED_FIELDS)
    if unknown:
        raise ValueError("policy inputs contain non-allowlisted fields")
    if len(rules) > MAX_RULES:
        raise ValueError("policy rule limit exceeded")
    parsed = [
        r if isinstance(r, PolicyRuleSpec) else PolicyRuleSpec.model_validate(r) for r in rules
    ]
    seen: set[str] = set()
    for rule in parsed:
        if rule.rule_id in seen:
            raise ValueError("duplicate policy rule id")
        seen.add(rule.rule_id)
    matching = [
        rule
        for rule in parsed
        if all(_compare(inputs.get(condition.field), condition) for condition in rule.conditions)
    ]
    if not matching:
        return PolicyEvaluation(
            default_outcome,
            (),
            ("DEFAULT_SAFE_OUTCOME",),
            "No policy rule matched; the configured safe default applies.",
        )
    priority = max(rule.priority for rule in matching)
    candidates = sorted(
        (rule for rule in matching if rule.priority == priority), key=lambda rule: rule.rule_id
    )
    outcome = max(candidates, key=lambda rule: _OUTCOME_PRECEDENCE[rule.outcome]).outcome
    return PolicyEvaluation(
        outcome,
        tuple(rule.rule_id for rule in candidates),
        tuple(rule.reason_code for rule in candidates),
        "; ".join(rule.explanation for rule in candidates),
    )
