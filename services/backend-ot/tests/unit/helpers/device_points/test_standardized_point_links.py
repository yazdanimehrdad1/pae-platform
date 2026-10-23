"""
Unit tests for the standardized point link check (helpers.device_points.standardized_point_links).

Invariant guarded: a link is set only from a STANDARDIZED point to an active NATIVE point on the
same device, and between power units (W, kW, MW) its scale_factor must convert the source's unit
into the link's; other quantities are taken as given. A rejected link leaves the point untouched.
Rows are in-memory ORM objects (no DB).
"""

from datetime import UTC, datetime

import pytest

from helpers.device_points.standardized_point_links import apply_point_link, power_scale_error
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

    def test_a_scale_that_does_not_convert_the_power_unit_is_rejected(self):
        point = standardized()
        with pytest.raises(ValidationError, match="expected 0.001"):
            apply_point_link(point, POWER_W, POWER_LINK.model_copy(update={"scale_factor": 1.0}))
        assert point.source_point_id is None


class TestPowerScaleError:
    @pytest.mark.parametrize(
        ("source_unit", "unit", "scale_factor"),
        [("W", "kW", 0.001), ("MW", "kW", 1000.0), ("kW", "kW", 1.0), ("kW", "W", 1000.0)],
    )
    def test_converting_scales_pass(self, source_unit: str, unit: str, scale_factor: float):
        assert power_scale_error(source_unit, unit, scale_factor) is None

    def test_a_wrong_scale_says_what_was_expected(self):
        assert power_scale_error("W", "kW", 1.0) == "scale_factor 1 doesn't turn W into kW (expected 0.001)"

    @pytest.mark.parametrize(
        ("source_unit", "unit"), [("%", "%"), ("kvar", "kvar"), (None, None), ("W", None), (None, "kW")]
    )
    def test_other_quantities_are_not_checked(self, source_unit: str | None, unit: str | None):
        assert power_scale_error(source_unit, unit, 2.0) is None
