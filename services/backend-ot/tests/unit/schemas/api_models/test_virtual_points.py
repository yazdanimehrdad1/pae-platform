"""Unit tests for schemas.api_models.virtual_points.

Invariant guarded: a virtual point definition is rejected at the API boundary (422) unless its
shape can be evaluated: each comparison has exactly one operand and each bit test a bit, groups
nest at most two levels, difference/ratio have exactly two inputs. (What a definition reads and
its labels: tests/unit/helpers/virtual_points/test_definition.py.)
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from schemas.api_models import (
    VirtualCalculationDefinition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
    VirtualPointDefinition,
)

DEFINITION = TypeAdapter(VirtualPointDefinition)


def condition(**fields: object) -> dict[str, object]:
    return {"point_id": 1, "operator": ">", "value": 1} | fields


def definition_with(*items: dict[str, object]) -> dict[str, object]:
    return {"kind": "condition", "cases": [{"output": 1, "when": {"match": "all", "items": list(items)}}]}


class TestConditionOperands:
    @pytest.mark.parametrize(
        "bad",
        [
            condition(value=None),                             # comparison with no operand
            condition(compare_point_id=2),                     # comparison with two operands
            condition(bit=1),                                  # comparison with a bit
            condition(operator="bit_set", value=None),         # bit test with no bit
            condition(operator="bit_set", bit=1),              # bit test with a value too
            condition(operator="bit_set", value=None, bit=64),  # bit out of range
            condition(operator="~="),                          # unknown operator
        ],
    )
    def test_invalid_condition_is_rejected(self, bad: dict[str, object]):
        with pytest.raises(ValidationError):
            DEFINITION.validate_python(definition_with(bad))

    def test_valid_forms(self):
        parsed = DEFINITION.validate_python(definition_with(
            condition(),
            condition(value=None, compare_point_id=2),
            condition(operator="bit_clear", value=None, bit=3),
        ))
        assert isinstance(parsed, VirtualConditionDefinition)


class TestGroupShape:
    def test_type_may_be_omitted_on_group_items(self):
        parsed = DEFINITION.validate_python(definition_with({"match": "any", "items": [condition()]}))
        assert isinstance(parsed, VirtualConditionDefinition)
        assert isinstance(parsed.cases[0].when.items[0], VirtualConditionGroup)

    def test_two_levels_nest_but_three_do_not(self):
        two = definition_with({"match": "any", "items": [condition()]})
        three = definition_with({"match": "any", "items": [{"match": "all", "items": [condition()]}]})
        DEFINITION.validate_python(two)
        with pytest.raises(ValidationError, match="nest at most 2"):
            DEFINITION.validate_python(three)

    def test_empty_group_and_no_cases_are_rejected(self):
        with pytest.raises(ValidationError):
            DEFINITION.validate_python(definition_with())
        with pytest.raises(ValidationError):
            DEFINITION.validate_python({"kind": "condition", "cases": []})


class TestCalculationShape:
    @pytest.mark.parametrize("function", ["difference", "ratio"])
    def test_two_input_functions_need_exactly_two(self, function: str):
        with pytest.raises(ValidationError, match="exactly 2 inputs"):
            DEFINITION.validate_python({"kind": "calculation", "function": function, "inputs": [1, 2, 3]})

    def test_aggregate_takes_one_or_more(self):
        parsed = DEFINITION.validate_python({"kind": "calculation", "function": "sum", "inputs": [1]})
        assert isinstance(parsed, VirtualCalculationDefinition)
        with pytest.raises(ValidationError):
            DEFINITION.validate_python({"kind": "calculation", "function": "sum", "inputs": []})

