"""What a virtual point definition reads and produces: its input points and its state labels.

Pure: works on the parsed definition models (schemas.api_models.virtual_points). Used by the save
path (checking inputs, deriving enum_detail), the read path (loading inputs) and the evaluator.
"""

from typing import assert_never

from schemas.api_models.virtual_points import (
    BIT_OPERATORS,
    VirtualCalculationDefinition,
    VirtualCondition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
    VirtualDefinition,
)


def referenced_point_ids(definition: VirtualDefinition) -> set[int]:
    """Every point a definition reads."""
    match definition:
        case VirtualCalculationDefinition():
            return set(definition.inputs)
        case VirtualConditionDefinition():
            return {point_id for case in definition.cases for point_id in condition_point_ids(case.when)}
        case _:
            assert_never(definition)


def bit_condition_point_ids(definition: VirtualDefinition) -> set[int]:
    """Points that a bit_set / bit_clear condition reads (they must be bitfields)."""
    match definition:
        case VirtualCalculationDefinition():
            return set()
        case VirtualConditionDefinition():
            return {point_id for case in definition.cases for point_id in bit_test_point_ids(case.when)}
        case _:
            assert_never(definition)


def condition_enum_detail(definition: VirtualConditionDefinition) -> dict[str, str] | None:
    """State labels for a condition point's enum_detail, or None when no case is labelled.
    The default's label wins for its output; otherwise the first labelled case's."""
    labels: dict[str, str] = {}
    if definition.default_label:
        labels[str(definition.default_output)] = definition.default_label
    for case in definition.cases:
        if case.label:
            labels.setdefault(str(case.output), case.label)
    return labels or None


def condition_point_ids(item: VirtualCondition | VirtualConditionGroup) -> set[int]:
    """Every point one comparison or group reads, including compared-with points and nested groups.
    Shared with alarm rules, which use the same comparisons and groups."""
    if isinstance(item, VirtualCondition):
        return {item.point_id} | ({item.compare_point_id} if item.compare_point_id is not None else set())
    return {point_id for child in item.items for point_id in condition_point_ids(child)}


def bit_test_point_ids(item: VirtualCondition | VirtualConditionGroup) -> set[int]:
    """Points a bit_set / bit_clear test reads, in one comparison or group (they must be bitfields)."""
    if isinstance(item, VirtualCondition):
        return {item.point_id} if item.operator in BIT_OPERATORS else set()
    return {point_id for child in item.items for point_id in bit_test_point_ids(child)}
