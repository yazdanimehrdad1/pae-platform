"""Unit tests for helpers.virtual_points.definition.

Invariant guarded: the points a definition reads include nested groups and compared points (the
save path validates them and the read path loads them); only bit tests need a bitfield; and a
condition's labelled cases become its enum_detail, for both definition kinds.
"""

from helpers.virtual_points.definition import (
    bit_condition_point_ids,
    condition_enum_detail,
    referenced_point_ids,
)
from schemas.api_models import (
    VirtualCalculationDefinition,
    VirtualCase,
    VirtualCondition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
)

CONDITION = VirtualConditionDefinition(
    kind="condition",
    cases=[
        VirtualCase(output=2, label="fault", when=VirtualConditionGroup(match="any", items=[
            VirtualCondition(point_id=1, operator="==", value=5),
            VirtualConditionGroup(match="all", items=[
                VirtualCondition(point_id=2, operator="bit_set", bit=7),
                VirtualCondition(point_id=3, operator=">", compare_point_id=4),
            ]),
        ])),
        VirtualCase(output=1, when=VirtualConditionGroup(match="all", items=[
            VirtualCondition(point_id=5, operator=">=", value=20),
        ])),
    ],
    default_output=0,
    default_label="idle",
)
CALCULATION = VirtualCalculationDefinition(kind="calculation", function="sum", inputs=[7, 8, 7])


class TestReferencedPointIds:
    def test_condition_includes_nested_and_compared_points(self):
        assert referenced_point_ids(CONDITION) == {1, 2, 3, 4, 5}

    def test_calculation_is_its_inputs(self):
        assert referenced_point_ids(CALCULATION) == {7, 8}


class TestBitConditionPointIds:
    def test_only_points_under_a_bit_test(self):
        assert bit_condition_point_ids(CONDITION) == {2}

    def test_a_calculation_has_none(self):
        assert bit_condition_point_ids(CALCULATION) == set()


class TestConditionEnumDetail:
    def test_labels_from_labelled_cases_and_the_default(self):
        assert condition_enum_detail(CONDITION) == {"0": "idle", "2": "fault"}

    def test_no_labels_means_no_enum_detail(self):
        unlabelled = CONDITION.model_copy(update={"default_label": None, "cases": CONDITION.cases[1:]})
        assert condition_enum_detail(unlabelled) is None
