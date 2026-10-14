"""
Unit tests for site_profiles.common.pv.pv_functions.

Guards the wiring around the pure PV math: the power point is read once, its readings and
unit reach the statistics, and a misdeclared call (threshold <= 0, a non-power unit) is a
SiteProfileConfigError. The historian read is faked at the module boundary.
"""

from datetime import UTC, datetime, timedelta

import pytest

import site_profiles.common.pv.pv_functions as pv_functions
from schemas.api_models import DevicePointResponse, PointTimeseries, TimeseriesPoint
from schemas.site_profiles import SiteContext, TimeWindow
from unit.site_fixtures import make_device, make_point, make_site
from utils.exceptions import SiteProfileConfigError

START = datetime(2026, 6, 21, 4, 0, tzinfo=UTC)
WINDOW = TimeWindow(start_time=START, end_time=START + timedelta(hours=8))
PV_POWER_POINT = make_point(11, 1, "active_power").model_copy(update={"unit": "W"})


def context() -> SiteContext:
    return SiteContext(
        site=make_site(), devices=[make_device(1, [PV_POWER_POINT], device_type="PV")]
    )


def fake_timeseries(monkeypatch: pytest.MonkeyPatch, values: list[float]) -> list[list[int]]:
    """Serve one reading per value, an hour apart, for each point; return the point ids of each read."""
    reads: list[list[int]] = []

    async def get_point_timeseries(
        ctx: SiteContext, points: list[DevicePointResponse], window: TimeWindow
    ) -> dict[int, PointTimeseries]:
        reads.append([point.id for point in points])
        return {
            point.id: PointTimeseries(
                id=point.id,
                name=point.name,
                data_type=point.data_type,
                unit=point.unit,
                timeseries=[
                    TimeseriesPoint(time=START + timedelta(hours=index), value=value)
                    for index, value in enumerate(values)
                ],
            )
            for point in points
        }

    monkeypatch.setattr(pv_functions, "spf_common_get_point_timeseries", get_point_timeseries)
    return reads


class TestPvPowerStats:
    async def test_reads_the_point_once_and_computes_in_kw(self, monkeypatch: pytest.MonkeyPatch):
        reads = fake_timeseries(monkeypatch, [0.0, 4000.0, 8000.0, 4000.0, 0.0])  # W

        stats = await pv_functions.spf_common_pv_power_stats(
            context(), PV_POWER_POINT, WINDOW, producing_threshold_kw=1.0
        )

        assert reads == [[11]]
        assert (stats.peak_kw, stats.energy_produced_kwh) == (8.0, pytest.approx(16.0))
        assert (stats.producing_hours, stats.average_producing_kw) == (2.0, pytest.approx(6.0))

    async def test_threshold_must_be_positive_before_reading(self, monkeypatch: pytest.MonkeyPatch):
        reads = fake_timeseries(monkeypatch, [])

        with pytest.raises(SiteProfileConfigError, match="producing_threshold_kw must be > 0"):
            await pv_functions.spf_common_pv_power_stats(
                context(), PV_POWER_POINT, WINDOW, producing_threshold_kw=0.0
            )
        assert reads == []

    async def test_non_power_unit_is_a_config_error(self, monkeypatch: pytest.MonkeyPatch):
        fake_timeseries(monkeypatch, [1.0, 1.0])
        energy_point = PV_POWER_POINT.model_copy(update={"unit": "kWh"})

        with pytest.raises(SiteProfileConfigError, match="Unsupported power unit"):
            await pv_functions.spf_common_pv_power_stats(
                context(), energy_point, WINDOW, producing_threshold_kw=1.0
            )
