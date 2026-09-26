"""
Unit tests for schemas.site_profiles.common.

Guards the query window every site function accepts (exactly one way to pick a window,
explicit timezones, ordered bounds) and SiteContext's point lookup by name.
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from schemas.api_models import (
    DevicePointResponse,
    DevicePointsCategoryGrouped,
    DeviceWithPoints,
    Location,
    SiteResponse,
)
from schemas.site_profiles import SiteContext, TimeWindowParams

START = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
END = START + timedelta(hours=2)


class TestTimeWindowParams:
    def test_explicit_bounds_resolve_to_utc(self):
        window = TimeWindowParams(
            start_time=datetime(2026, 1, 15, 4, 0), end_time=datetime(2026, 1, 15, 6, 0), tz="PT"
        ).resolve_window()
        assert window.start_time == START
        assert window.end_time == END

    def test_display_renders_in_requested_zone(self):
        window = TimeWindowParams(start_time=START, end_time=END, tz="UTC").resolve_window()
        assert window.display(START).utcoffset() == timedelta(0)

    def test_time_range_spans_the_token(self):
        window = TimeWindowParams(time_range="1D").resolve_window()
        assert window.end_time - window.start_time == timedelta(days=1)

    def test_missing_end_defaults_to_now(self):
        window = TimeWindowParams(start_time=START).resolve_window()
        assert window.end_time > window.start_time

    def test_no_window_is_rejected(self):
        with pytest.raises(ValidationError, match="Provide time_range"):
            TimeWindowParams()

    def test_time_range_with_bounds_is_rejected(self):
        with pytest.raises(ValidationError, match="not both"):
            TimeWindowParams(time_range="1D", start_time=START)

    def test_naive_bound_without_tz_is_rejected(self):
        with pytest.raises(ValidationError, match="no timezone"):
            TimeWindowParams(start_time=datetime(2026, 1, 15, 12, 0))

    def test_unknown_tz_is_rejected(self):
        with pytest.raises(ValidationError, match="Unknown timezone"):
            TimeWindowParams(time_range="1D", tz="Nowhere/Nothing")

    def test_start_not_before_end_is_rejected(self):
        with pytest.raises(ValidationError, match="before end_time"):
            TimeWindowParams(start_time=END, end_time=START)


def point(point_id: int, device_id: int, name: str) -> DevicePointResponse:
    return DevicePointResponse(
        id=point_id, site_id=1001, device_id=device_id, name=name, address=point_id, size=1, data_type="uint16"
    )


def device(device_id: int, name: str, points: list[DevicePointResponse]) -> DeviceWithPoints:
    return DeviceWithPoints(
        device_id=device_id,
        site_id=1001,
        name=name,
        type="PV",
        protocol="modbus",
        host="10.0.0.1",
        port=502,
        server_address=1,
        created_at=START,
        updated_at=START,
        points=DevicePointsCategoryGrouped(native=points),
    )


class TestSiteContextPointsNamed:
    def make_context(self) -> SiteContext:
        site = SiteResponse(
            site_id=1001,
            client_id="c",
            name="Site",
            location=Location(street="1 Main St", city="Fresno", state="CA", zip_code=93701),
            operator="op",
            capacity="1MW",
            device_count=2,
            profile="default",
            created_at=START,
            updated_at=START,
            last_update=START,
        )
        return SiteContext(
            site=site,
            devices=[
                device(1, "device_1", [point(10, 1, "active_power"), point(11, 1, "inverter_state")]),
                device(2, "device_2", [point(20, 2, "active_power")]),
            ],
        )

    def test_finds_the_point_on_every_device(self):
        assert [p.id for p in self.make_context().points_named("active_power")] == [10, 20]

    def test_limits_to_given_devices(self):
        ctx = self.make_context()
        assert [p.id for p in ctx.points_named("active_power", [ctx.devices[1]])] == [20]

    def test_unknown_name_is_empty(self):
        assert self.make_context().points_named("nope") == []
