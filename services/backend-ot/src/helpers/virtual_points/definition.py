"""What a virtual point definition reads and produces: its input points and its state labels.

Pure: works on the parsed definition models (schemas.api_models.virtual_points). Used by the save
path (checking inputs, deriving enum_detail), the read path (loading inputs) and the evaluator.
"""

from typing import assert_never

from schemas.api_models.virtual_points import (
    BIT_OPERATORS,
    VirtualCalculationDefinition,
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
            return {point_id for case in definition.cases for point_id in _group_point_ids(case.when)}
        case _:
            assert_never(definition)


def bit_condition_point_ids(definition: VirtualDefinition) -> set[int]:
    """Points that a bit_set / bit_clear condition reads (they must be bitfields)."""
    match definition:
        case VirtualCalculationDefinition():
            return set()
        case VirtualConditionDefinition():
            return {point_id for case in definition.cases for point_id in _group_bit_point_ids(case.when)}
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


def _group_point_ids(group: VirtualConditionGroup) -> set[int]:
    point_ids: set[int] = set()
    for item in group.items:
        if isinstance(item, VirtualConditionGroup):
            point_ids |= _group_point_ids(item)
        else:
            point_ids.add(item.point_id)
            if item.compare_point_id is not None:
                point_ids.add(item.compare_point_id)
    return point_ids


def _group_bit_point_ids(group: VirtualConditionGroup) -> set[int]:
    point_ids: set[int] = set()
    for item in group.items:
        if isinstance(item, VirtualConditionGroup):
            point_ids |= _group_bit_point_ids(item)
        elif item.operator in BIT_OPERATORS:
            point_ids.add(item.point_id)
    return point_ids
