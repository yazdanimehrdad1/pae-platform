"""
Unit tests for site_profiles.common.spf_point_functions.

Invariant guarded: an SPF point is found by device name and point name (a missing device or point,
or a STANDARDIZED point not linked yet, is a 404 naming it); spf_common_sum_points reads all the
points in one historian query and, at each poll timestamp, adds value x scale x sign over the
points; readings of one poll a few milliseconds apart share that timestamp, and a timestamp where
a point has no value is left out, never part-summed.
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

import site_profiles.common.spf_point_functions as spf_point_functions
from schemas.api_models import (
    DevicePointResponse,
    DevicePointsCategoryGrouped,
    DeviceWithPoints,
    PointTimeseries,
    TimeseriesPoint,
)
from schemas.internal_models import TimestampedValue
from schemas.site_profiles import SiteContext, TimeWindow
from site_profiles.common.spf_point_functions import (
    spf_common_find_device_point,
    spf_common_points_series,
    spf_common_sum_points,
)
from site_profiles.declarations.spf_point import SpfPoint
from unit.site_fixtures import make_device, make_point, make_site
from utils.exceptions import NotFoundError

START = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
POLL = timedelta(seconds=20)
WINDOW = TimeWindow(start_time=START, end_time=START + timedelta(hours=1))


def device(device_id: int, name: str, native: list[str], standardized: dict[str, int | None]) -> DeviceWithPoints:
    """A device with NATIVE points `native` and STANDARDIZED points {name: linked source id or None}."""
    native_points = [make_point(device_id * 10 + index, device_id, point) for index, point in enumerate(native)]
    standardized_points = [
        make_point(device_id * 10 + 5 + index, device_id, point).model_copy(
            update={"category": "STANDARDIZED", "source_point_id": source}
        )
        for index, (point, source) in enumerate(standardized.items())
    ]
    return make_device(device_id, []).model_copy(
        update={"name": name, "points": DevicePointsCategoryGrouped(native=native_points, standardized=standardized_points)}
    )


BESS1 = device(1, "bess1", ["W", "Var"], {"BESS_ACTIVE_POWER": 10, "BESS_STATE_OF_CHARGE": None})
BESS2 = device(2, "bess2", ["W", "Var"], {"BESS_ACTIVE_POWER": 20})
PV1 = device(3, "pv1", ["W", "Var"], {"PV_ACTIVE_POWER": 30})
CONTEXT = SiteContext(site=make_site("powerflow_2bess_1pv"), devices=[BESS1, BESS2, PV1])


def fake_readings(
    monkeypatch: pytest.MonkeyPatch, values_by_point: dict[int, list[tuple[timedelta, float | None]]]
) -> list[list[int]]:
    """Serve readings {point id: [(time after START, value)]}; returns the point ids of each read."""
    reads: list[list[int]] = []

    async def get_point_timeseries(
        ctx: SiteContext, points: list[DevicePointResponse], window: TimeWindow
    ) -> dict[int, PointTimeseries]:
        reads.append([point.id for point in points])
        return {
            point.id: PointTimeseries(
                id=point.id,
                name=point.name,
                data_type="int16",
                timeseries=[
                    TimeseriesPoint(time=START + offset, value=value) for offset, value in values_by_point.get(point.id, [])
                ],
            )
            for point in points
        }

    monkeypatch.setattr(spf_point_functions, "spf_common_get_point_timeseries", get_point_timeseries)
    return reads


def at_poll(index: int, milliseconds: int = 0) -> timedelta:
    return POLL * index + timedelta(milliseconds=milliseconds)


class TestSpfPoint:
    def test_category_is_required_and_one_of_the_point_categories(self):
        with pytest.raises(ValidationError):
            SpfPoint(device="bess1", point="W", scale=1, sign=1)
        with pytest.raises(ValidationError):
            SpfPoint(device="bess1", point="W", category="CALCULATED", scale=1, sign=1)


class TestFindDevicePoint:
    def test_finds_a_native_point_or_a_linked_standardized_point(self):
        assert spf_common_find_device_point(CONTEXT, SpfPoint(device="bess1", point="Var", category="NATIVE", scale=1, sign=1)).id == 11
        found = spf_common_find_device_point(CONTEXT, SpfPoint(device="bess1", point="BESS_ACTIVE_POWER", category="STANDARDIZED", scale=1, sign=1))
        assert (found.id, found.name) == (15, "BESS_ACTIVE_POWER")

    def test_an_unlinked_standardized_point_is_a_404(self):
        with pytest.raises(NotFoundError, match="BESS_STATE_OF_CHARGE isn't linked"):
            spf_common_find_device_point(CONTEXT, SpfPoint(device="bess1", point="BESS_STATE_OF_CHARGE", category="STANDARDIZED", scale=1, sign=1))

    def test_a_missing_device_or_point_is_a_404_naming_it(self):
        with pytest.raises(NotFoundError, match="no device 'load1'"):
            spf_common_find_device_point(CONTEXT, SpfPoint(device="load1", point="W", category="NATIVE", scale=1, sign=1))
        with pytest.raises(NotFoundError, match="'bess1' has no point 'VAR'"):
            spf_common_find_device_point(CONTEXT, SpfPoint(device="bess1", point="VAR", category="NATIVE", scale=1, sign=1))


class TestSumPoints:
    ASSETS = (
        SpfPoint(device="bess1", point="BESS_ACTIVE_POWER", category="STANDARDIZED", scale=1, sign=1),
        SpfPoint(device="bess2", point="BESS_ACTIVE_POWER", category="STANDARDIZED", scale=1, sign=1),
        SpfPoint(device="pv1", point="PV_ACTIVE_POWER", category="STANDARDIZED", scale=1, sign=1),
    )

    async def test_sums_the_points_at_each_poll_timestamp_in_one_read(self, monkeypatch: pytest.MonkeyPatch):
        # Live polls of the simulated site: the devices of one poll are read milliseconds apart.
        reads = fake_readings(
            monkeypatch,
            {
                15: [(at_poll(0, 560), -1129.0), (at_poll(1, 548), -1721.0)],
                25: [(at_poll(0, 556), -1412.0), (at_poll(1, 545), -1639.0)],
                35: [(at_poll(0, 551), 2122.0), (at_poll(1, 563), 2117.0)],
            },
        )
        values = await spf_common_sum_points(CONTEXT, self.ASSETS, WINDOW)
        assert [(value.time, value.value) for value in values] == [
            (START + timedelta(seconds=1), -419.0),
            (START + POLL + timedelta(seconds=1), -1243.0),
        ]
        assert reads == [[15, 25, 35]]

    async def test_applies_each_points_scale_and_sign(self, monkeypatch: pytest.MonkeyPatch):
        fake_readings(monkeypatch, {10: [(at_poll(0), 2000.0)], 20: [(at_poll(0), 500.0)]})
        points = (
            SpfPoint(device="bess1", point="W", category="NATIVE", scale=0.001, sign=1),  # 2000 W out = 2 kW
            SpfPoint(device="bess2", point="W", category="NATIVE", scale=0.001, sign=-1),  # 500 W read as import = -0.5 kW
        )
        values = await spf_common_sum_points(CONTEXT, points, WINDOW)
        assert [value.value for value in values] == [1.5]

    async def test_a_timestamp_missing_a_point_is_left_out(self, monkeypatch: pytest.MonkeyPatch):
        fake_readings(
            monkeypatch,
            {
                15: [(at_poll(0), 1.0), (at_poll(1), 2.0), (at_poll(2), 3.0)],
                25: [(at_poll(0), 10.0), (at_poll(1), None), (at_poll(2), 30.0)],
                35: [(at_poll(0), 100.0), (at_poll(2), 300.0)],
            },
        )
        values = await spf_common_sum_points(CONTEXT, self.ASSETS, WINDOW)
        assert [(value.time, value.value) for value in values] == [(START, 111.0), (START + POLL * 2, 333.0)]

    async def test_no_readings_gives_no_values(self, monkeypatch: pytest.MonkeyPatch):
        fake_readings(monkeypatch, {})
        assert await spf_common_sum_points(CONTEXT, self.ASSETS, WINDOW) == []

    async def test_a_missing_point_is_a_404_before_reading(self, monkeypatch: pytest.MonkeyPatch):
        reads = fake_readings(monkeypatch, {})
        with pytest.raises(NotFoundError, match="no device 'pv2'"):
            await spf_common_sum_points(CONTEXT, (SpfPoint(device="pv2", point="W", category="NATIVE", scale=1, sign=1),), WINDOW)
        assert reads == []


class TestPointsSeries:
    def test_a_computed_series_has_id_0_and_the_values_in_order(self):
        values = [
            TimestampedValue(time=START, value=-419.0),
            TimestampedValue(time=START + POLL, value=-1243.0),
        ]
        series = spf_common_points_series(values, "assets active power (kW)", "kW")
        assert (series.id, series.name, series.unit, series.count) == (0, "assets active power (kW)", "kW", 2)
        assert [(sample.time, sample.value) for sample in series.timeseries] == [(START, -419.0), (START + POLL, -1243.0)]
