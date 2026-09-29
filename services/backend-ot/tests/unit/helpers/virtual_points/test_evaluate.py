"""Unit tests for helpers.virtual_points.evaluate.

Invariant guarded: a virtual point's value is a pure function of one cycle's inputs, with the same
comparison and bit semantics as the UI, and no value at all (None) when an input is missing or a
ratio would divide by zero, rather than a made-up number.
"""

import pytest

from helpers.virtual_points import evaluate_virtual_point
from schemas.api_models import (
    VirtualCalculationDefinition,
    VirtualCase,
    VirtualCondition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
)


def calculation(function: str, *inputs: int, scale: float = 1.0, offset: float = 0.0) -> VirtualCalculationDefinition:
    return VirtualCalculationDefinition(
        kind="calculation", function=function, inputs=list(inputs), scale=scale, offset=offset
    )


def one_case(group: VirtualConditionGroup) -> VirtualConditionDefinition:
    return VirtualConditionDefinition(kind="condition", cases=[VirtualCase(output=1, when=group)], default_output=0)


def compare(point_id: int, operator: str, value: float) -> VirtualCondition:
    return VirtualCondition(point_id=point_id, operator=operator, value=value)


def bit_test(point_id: int, operator: str, bit: int) -> VirtualConditionDefinition:
    return one_case(VirtualConditionGroup(match="all", items=[VirtualCondition(point_id=point_id, operator=operator, bit=bit)]))


class TestCalculation:
    @pytest.mark.parametrize(
        ("function", "expected"),
        [("sum", 12.0), ("avg", 4.0), ("min", 2.0), ("max", 6.0)],
    )
    def test_aggregates(self, function: str, expected: float):
        assert evaluate_virtual_point(calculation(function, 1, 2, 3), {1: 4.0, 2: 2.0, 3: 6.0}) == expected

    def test_difference_and_ratio_use_input_order(self):
        values = {1: 10.0, 2: 4.0}
        assert evaluate_virtual_point(calculation("difference", 1, 2), values) == 6.0
        assert evaluate_virtual_point(calculation("ratio", 1, 2), values) == 2.5

    def test_scale_then_offset(self):
        assert evaluate_virtual_point(calculation("sum", 1, scale=0.001, offset=1.0), {1: 2000.0}) == 3.0

    def test_ratio_by_zero_is_none(self):
        assert evaluate_virtual_point(calculation("ratio", 1, 2), {1: 5.0, 2: 0.0}) is None

    def test_missing_or_null_input_is_none(self):
        assert evaluate_virtual_point(calculation("sum", 1, 2), {1: 5.0}) is None
        assert evaluate_virtual_point(calculation("sum", 1, 2), {1: 5.0, 2: None}) is None


class TestConditionOperators:
    @pytest.mark.parametrize(
        ("operator", "value", "holds"),
        [
            (">", 5, False), (">", 4, True),
            ("<", 6, True), ("<", 5, False),
            (">=", 5, True), ("<=", 5, True),
            ("==", 5, True), ("!=", 5, False), ("!=", 4, True),
        ],
    )
    def test_comparison_to_a_value(self, operator: str, value: float, holds: bool):
        definition = one_case(VirtualConditionGroup(match="all", items=[compare(1, operator, value)]))
        assert evaluate_virtual_point(definition, {1: 5.0}) == (1.0 if holds else 0.0)

    def test_comparison_to_another_point(self):
        condition = VirtualCondition(point_id=1, operator=">", compare_point_id=2)
        definition = one_case(VirtualConditionGroup(match="all", items=[condition]))
        assert evaluate_virtual_point(definition, {1: 5.0, 2: 3.0}) == 1.0
        assert evaluate_virtual_point(definition, {1: 5.0, 2: 9.0}) == 0.0
        assert evaluate_virtual_point(definition, {1: 5.0}) is None

    @pytest.mark.parametrize(("raw", "bit_set"), [(0b1000, True), (0b0111, False), (2.0**40, False)])
    def test_bit_set_and_clear(self, raw: float, bit_set: bool):
        assert evaluate_virtual_point(bit_test(1, "bit_set", 3), {1: raw}) == (1.0 if bit_set else 0.0)
        assert evaluate_virtual_point(bit_test(1, "bit_clear", 3), {1: raw}) == (0.0 if bit_set else 1.0)

    def test_high_bits_read_correctly(self):
        assert evaluate_virtual_point(bit_test(1, "bit_set", 40), {1: 2.0**40}) == 1.0


class TestConditionStructure:
    def test_all_needs_every_item_and_any_needs_one(self):
        items = [compare(1, ">", 0), compare(2, ">", 0)]
        values = {1: 1.0, 2: -1.0}
        assert evaluate_virtual_point(one_case(VirtualConditionGroup(match="all", items=items)), values) == 0.0
        assert evaluate_virtual_point(one_case(VirtualConditionGroup(match="any", items=items)), values) == 1.0

    def test_nested_group(self):
        # point1 > 0 AND (point2 == 3 OR point3 == 3)
        group = VirtualConditionGroup(match="all", items=[
            compare(1, ">", 0),
            VirtualConditionGroup(match="any", items=[compare(2, "==", 3), compare(3, "==", 3)]),
        ])
        assert evaluate_virtual_point(one_case(group), {1: 1.0, 2: 0.0, 3: 3.0}) == 1.0
        assert evaluate_virtual_point(one_case(group), {1: 1.0, 2: 0.0, 3: 0.0}) == 0.0

    def test_first_matching_case_wins_and_default_otherwise(self):
        definition = VirtualConditionDefinition(
            kind="condition",
            cases=[
                VirtualCase(output=2, when=VirtualConditionGroup(match="all", items=[compare(1, ">", 10)])),
                VirtualCase(output=1, when=VirtualConditionGroup(match="all", items=[compare(1, ">", 0)])),
            ],
            default_output=7,
        )
        assert evaluate_virtual_point(definition, {1: 20.0}) == 2.0
        assert evaluate_virtual_point(definition, {1: 5.0}) == 1.0
        assert evaluate_virtual_point(definition, {1: -5.0}) == 7.0

    def test_a_missing_input_in_any_case_is_none(self):
        definition = VirtualConditionDefinition(
            kind="condition",
            cases=[
                VirtualCase(output=1, when=VirtualConditionGroup(match="all", items=[compare(1, ">", 0)])),
                VirtualCase(output=2, when=VirtualConditionGroup(match="all", items=[compare(2, ">", 0)])),
            ],
        )
        assert evaluate_virtual_point(definition, {1: 5.0}) is None
