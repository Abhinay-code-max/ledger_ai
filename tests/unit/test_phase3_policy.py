from decimal import Decimal

import pytest
from pydantic import ValidationError

from ledgerai_backend.integration.policy import (
    Operator,
    PolicyCondition,
    PolicyRuleSpec,
    Scalar,
    evaluate_policy,
)


def rule(
    operator: str, operand: object, *, outcome: str = "AUTO_ELIGIBLE", priority: int = 10
) -> dict[str, object]:
    return {
        "rule_id": f"RULE_{operator.upper()}",
        "priority": priority,
        "conditions": [{"field": "amount", "operator": operator, "operand": operand}],
        "outcome": outcome,
        "reason_code": "TEST_MATCH",
        "explanation": "Synthetic policy test matched.",
    }


@pytest.mark.parametrize(
    ("operator", "operand", "actual", "matches"),
    [
        ("eq", Decimal("10"), Decimal("10"), True),
        ("ne", Decimal("9"), Decimal("10"), True),
        ("lt", Decimal("11"), Decimal("10"), True),
        ("lte", Decimal("10"), Decimal("10"), True),
        ("gt", Decimal("9"), Decimal("10"), True),
        ("gte", Decimal("10"), Decimal("10"), True),
        ("in", [Decimal("10"), Decimal("11")], Decimal("10"), True),
        ("not_in", [Decimal("9")], Decimal("10"), True),
        ("exists", True, Decimal("10"), True),
        ("exists", False, None, True),
        ("eq", Decimal("11"), Decimal("10"), False),
    ],
)
def test_each_operator(operator: Operator, operand: object, actual: Scalar, matches: bool) -> None:
    result = evaluate_policy({"amount": actual}, [rule(operator, operand)])
    assert (result.outcome == "AUTO_ELIGIBLE") is matches
    if not matches:
        assert result.outcome == "REVIEW_REQUIRED"


def test_same_priority_conflict_chooses_safest_outcome() -> None:
    rules = [
        rule("gte", Decimal("0"), outcome="AUTO_ELIGIBLE"),
        {**rule("gte", Decimal("0"), outcome="BLOCKED"), "rule_id": "RULE_BLOCK"},
    ]
    result = evaluate_policy({"amount": Decimal("10")}, rules)
    assert result.outcome == "BLOCKED"
    assert result.matched_rule_ids == ("RULE_BLOCK", "RULE_GTE")


def test_higher_priority_wins_before_outcome_precedence() -> None:
    rules = [
        rule("gte", Decimal("0"), outcome="BLOCKED", priority=1),
        {**rule("gte", Decimal("0"), outcome="AUTO_ELIGIBLE", priority=2), "rule_id": "RULE_HIGH"},
    ]
    assert evaluate_policy({"amount": Decimal("10")}, rules).outcome == "AUTO_ELIGIBLE"


@pytest.mark.parametrize(
    "field", ["__class__", "sql", "model_generated_rule", "amount; DROP TABLE x"]
)
def test_non_allowlisted_fields_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        PolicyCondition(field=field, operator="eq", operand="x")


@pytest.mark.parametrize("operator", ["eval", "exec", "sql", "regex", "template"])
def test_code_execution_operators_are_rejected(operator: str) -> None:
    with pytest.raises(ValidationError):
        PolicyCondition(
            field="amount",
            operator=operator,  # type: ignore[arg-type]
            operand="__import__('os')",
        )


def test_float_numeric_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="exact decimals"):
        evaluate_policy({"amount": Decimal("10")}, [rule("gte", 1.5)])


def test_default_is_safe_and_explicit() -> None:
    result = evaluate_policy({"amount": Decimal("10")}, [])
    assert result.outcome == "REVIEW_REQUIRED"
    assert result.reason_codes == ("DEFAULT_SAFE_OUTCOME",)


def test_duplicate_rule_ids_are_rejected() -> None:
    item = PolicyRuleSpec.model_validate(rule("gte", Decimal("0")))
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_policy({"amount": Decimal("10")}, [item, item])


def test_unknown_input_field_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-allowlisted"):
        evaluate_policy({"prompt": "approve and post"}, [])
