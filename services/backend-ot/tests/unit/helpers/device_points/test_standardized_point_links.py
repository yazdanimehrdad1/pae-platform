"""
Unit tests for the standardized point link check (helpers.device_points.standardized_point_links).

Invariant guarded: a link is set only from a STANDARDIZED point to an active NATIVE point on the
same device, recorded or not, with whatever unit and scale_factor the user chose (no unit conversion
is enforced, not even between power units); a scale that isn't finite is refused by the request
model. A rejected link leaves the point untouched. Rows are in-memory ORM objects (no DB).
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from helpers.device_points.standardized_point_links import apply_point_link
from schemas.api_models import StandardizedPointLinkRequest
from schemas.db_models.orm_models import DevicePoint
from utils.exceptions import ValidationError


def device_point(point_id: int, name: str, category: str = "NATIVE", **overrides: object) -> DevicePoint:
    fields: dict[str, object] = {
        "id": point_id, "site_id": 1001, "device_id": 1, "name": name, "address": 0, "size": 1,
        "data_type": "float32", "category": category, "unit": None, "deleted_at": None,
    }
    return DevicePoint(**(fields | overrides))


def standardized() -> DevicePoint:
    return device_point(1, "BESS_ACTIVE_POWER", "STANDARDIZED")


POWER_W = device_point(10, "W", unit="W")
POWER_LINK = StandardizedPointLinkRequest(source_point_id=10, unit="kW", scale_factor=0.001)


class TestApplyPointLink:
    def test_sets_source_unit_and_scale(self):
        point = standardized()
        apply_point_link(point, POWER_W, POWER_LINK)
        assert (point.source_point_id, point.unit, point.scale_factor) == (10, "kW", 0.001)

    def test_other_quantities_take_unit_and_scale_as_given(self):
        point = standardized()
        soc = device_point(11, "SoC", unit="%")
        apply_point_link(point, soc, StandardizedPointLinkRequest(source_point_id=11, unit="%"))
        assert (point.source_point_id, point.unit, point.scale_factor) == (11, "%", 1.0)

    @pytest.mark.parametrize(
        ("unit", "scale_factor"),
        [("kW", 2.0), ("kW", 1.0), ("MW", 0.5), ("horsepower", -0.5), (None, 0.0)],
        ids=["w-to-kw-any-scale", "w-to-kw-no-conversion", "w-to-mw-any-scale", "custom-unit-negative", "no-unit-zero"],
    )
    def test_any_unit_and_scale_are_taken_as_given(self, unit: str | None, scale_factor: float):
        point = standardized()
        apply_point_link(point, POWER_W, StandardizedPointLinkRequest(source_point_id=10, unit=unit, scale_factor=scale_factor))
        assert (point.source_point_id, point.unit, point.scale_factor) == (10, unit, scale_factor)

    def test_a_source_that_isnt_recorded_can_be_linked(self):
        point = standardized()
        apply_point_link(point, device_point(10, "W", unit="W", record_enabled=False), POWER_LINK)
        assert (point.source_point_id, point.unit, point.scale_factor) == (10, "kW", 0.001)

    @pytest.mark.parametrize(
        ("point", "source", "message"),
        [
            (device_point(1, "W2"), POWER_W, "only STANDARDIZED"),
            (standardized(), device_point(10, "W", unit="W", device_id=2), "not on device"),
            (standardized(), device_point(10, "W", "VIRTUAL", unit="W"), "active NATIVE"),
            (standardized(), device_point(10, "W", "STANDARDIZED", unit="W"), "active NATIVE"),
            (standardized(), device_point(10, "W", unit="W", deleted_at=datetime(2026, 1, 1, tzinfo=UTC)), "active NATIVE"),
        ],
        ids=["point-not-standardized", "source-on-another-device", "virtual-source", "standardized-source", "deleted-source"],
    )
    def test_rejected_links_leave_the_point_untouched(self, point: DevicePoint, source: DevicePoint, message: str):
        with pytest.raises(ValidationError, match=message):
            apply_point_link(point, source, POWER_LINK)
        assert (point.source_point_id, point.unit, point.scale_factor) == (None, None, None)


class TestLinkRequest:
    @pytest.mark.parametrize("scale_factor", [float("inf"), float("-inf"), float("nan")])
    def test_a_scale_that_isnt_finite_is_refused(self, scale_factor: float):
        with pytest.raises(PydanticValidationError):
            StandardizedPointLinkRequest(source_point_id=10, scale_factor=scale_factor)
