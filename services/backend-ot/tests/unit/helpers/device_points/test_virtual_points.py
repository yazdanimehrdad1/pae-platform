"""Unit tests for helpers.device_points.virtual_points (the DB-free parts).

Invariant guarded: a virtual point's storage follows its kind (a condition is an enum16 labelled
by its cases, a calculation a float32), it has no register (address 0, no poll_kind), and the
definition is kept as the parsed model (the column type stores it as JSON).
"""

from helpers.device_points.virtual_points import new_virtual_point, virtual_point_storage
from schemas.api_models import (
    VirtualCalculationDefinition,
    VirtualCase,
    VirtualCondition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
    VirtualPointCreateRequest,
)

CONDITION = VirtualConditionDefinition(
    kind="condition",
    cases=[VirtualCase(output=1, label="on", when=VirtualConditionGroup(match="all", items=[
        VirtualCondition(point_id=1, operator=">", value=0),
    ]))],
    default_label="off",
)
CALCULATION = VirtualCalculationDefinition(kind="calculation", function="sum", inputs=[1, 2])


class TestVirtualPointStorage:
    def test_condition_is_a_labelled_enum16(self):
        assert virtual_point_storage(CONDITION) == ("enum16", {"0": "off", "1": "on"})

    def test_calculation_is_a_float32(self):
        assert virtual_point_storage(CALCULATION) == ("float32", None)


class TestNewVirtualPoint:
    def test_row_has_no_register_and_stores_the_definition(self):
        row = new_virtual_point(1, 2, VirtualPointCreateRequest(name="V", unit="kW", definition=CALCULATION))
        assert (row.category, row.address, row.poll_kind, row.data_type, row.size) == ("VIRTUAL", 0, None, "float32", 2)
        assert row.virtual_definition == CALCULATION
        assert (row.site_id, row.device_id, row.name, row.unit) == (1, 2, "V", "kW")
