"""Evaluate a virtual point's definition against one set of input values (one point in time).

Pure: no I/O. Semantics match the UI (web-plusdas):
- comparisons behave like the alarm rule engine's `compare` (`features/alarms/lib/ruleEngine.ts`);
- a bit is `(round(raw) >> bit) & 1`, like `decodeBit` (`shared/lib/discretePoints.ts`).

A definition that reads a point with no value yields None (no sample at that time), and so
does a ratio whose divisor is 0.
"""

from collections.abc import Mapping
from typing import assert_never

from helpers.virtual_points.definition import referenced_point_ids
from schemas.api_models.virtual_points import (
    VirtualCalculationDefinition,
    VirtualCondition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
    VirtualDefinition,
)


def evaluate_virtual_point(definition: VirtualDefinition, values: Mapping[int, float | None]) -> float | None:
    """The virtual point's value for one set of input values, or None when an input has no value."""
    known: dict[int, float] = {}
    for point_id in referenced_point_ids(definition):
        value = values.get(point_id)
        if value is None:
            return None
        known[point_id] = value

    match definition:
        case VirtualCalculationDefinition():
            return _calculate(definition, known)
        case VirtualConditionDefinition():
            return _first_matching_output(definition, known)
        case _:
            assert_never(definition)


def _first_matching_output(definition: VirtualConditionDefinition, values: Mapping[int, float]) -> float:
    for case in definition.cases:
        if group_holds(case.when, values):
            return float(case.output)
    return float(definition.default_output)


def _calculate(definition: VirtualCalculationDefinition, values: Mapping[int, float]) -> float | None:
    inputs = [values[point_id] for point_id in definition.inputs]
    match definition.function:
        case "sum":
            result = sum(inputs)
        case "avg":
            result = sum(inputs) / len(inputs)
        case "min":
            result = min(inputs)
        case "max":
            result = max(inputs)
        case "difference":
            result = inputs[0] - inputs[1]
        case "ratio":
            if inputs[1] == 0:
                return None
            result = inputs[0] / inputs[1]
    return result * definition.scale + definition.offset


def group_holds(group: VirtualConditionGroup, values: Mapping[int, float]) -> bool:
    """Whether an ALL/ANY group holds for these values (every point it reads must be present).
    Shared with the alarm engine."""
    results = (
        group_holds(item, values) if isinstance(item, VirtualConditionGroup) else condition_holds(item, values)
        for item in group.items
    )
    return all(results) if group.match == "all" else any(results)


def condition_holds(condition: VirtualCondition, values: Mapping[int, float]) -> bool:
    """Whether one comparison or bit test holds for these values. Shared with the alarm engine."""
    value = values[condition.point_id]
    if condition.operator in ("bit_set", "bit_clear"):
        assert condition.bit is not None  # guaranteed by VirtualCondition's validator
        bit_is_set = (round(value) >> condition.bit) & 1 == 1
        return bit_is_set if condition.operator == "bit_set" else not bit_is_set

    other = values[condition.compare_point_id] if condition.compare_point_id is not None else condition.value
    assert other is not None  # guaranteed by VirtualCondition's validator
    match condition.operator:
        case ">":
            return value > other
        case "<":
            return value < other
        case ">=":
            return value >= other
        case "<=":
            return value <= other
        case "==":
            return value == other
        case _:
            return value != other
