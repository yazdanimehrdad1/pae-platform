"""Unit tests for which points the Modbus poller decodes (helpers.modbus.modbus_data_mapping).

Invariant guarded: only NATIVE points are decoded from the register map. STANDARDIZED and VIRTUAL
points are derived from stored readings, never from registers. (Before this, both got bogus
readings from whatever sat at their placeholder addresses 0-2 every cycle.)
"""

from datetime import UTC, datetime

import pytest

from helpers.modbus.modbus_data_mapping import map_modbus_data_to_device_points
from schemas.db_models.orm_models import DevicePoint
from schemas.internal_models import RegisterMap

NOW = datetime(2026, 9, 27, 10, 0, 0, tzinfo=UTC)


def point(point_id: int, category: str) -> DevicePoint:
    return DevicePoint(
        id=point_id, site_id=1, device_id=1, name=f"p{point_id}", address=0, size=1,
        data_type="uint16", category=category,
    )


class TestOnlyNativePointsAreDecoded:
    @pytest.mark.parametrize("category", ["STANDARDIZED", "VIRTUAL"])
    def test_derived_point_gets_no_reading_from_the_register_map(self, category: str):
        readings = map_modbus_data_to_device_points(
            timestamp_dt=NOW,
            device_points_list=[point(1, "NATIVE"), point(2, category)],
            register_map=RegisterMap(values={0: 42}),
        )
        assert [(reading.device_point_id, reading.derived_value) for reading in readings] == [(1, 42.0)]
