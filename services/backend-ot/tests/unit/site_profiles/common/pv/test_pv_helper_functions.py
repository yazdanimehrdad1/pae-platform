"""
Unit tests for site_profiles.common.pv.pv_helper_functions.

Guards the PV power statistics on a one-day profile: energy produced and the night standby
draw are split by sign, peak is the maximum, the whole-window average and minimum include the
night, and the producing-hours average and minimum leave it (and the dawn/dusk intervals) out.
Also guards the sign flip, unit conversion, null and empty input, and a bad threshold or unit.
"""

from datetime import UTC, datetime, timedelta

import pytest

from schemas.api_models import TimeseriesPoint
from site_profiles.common.pv.pv_helper_functions import spf_common_pv_power_stats_from_samples

START = datetime(2026, 6, 21, 4, 0, tzinfo=UTC)

# hourly, kW: standby at night, ramp up to 10 kW at noon, back down
DAY_KW = [-0.1, 0.0, 2.0, 6.0, 10.0, 6.0, 2.0, 0.0, -0.1]


def hourly_samples(values: list[float | None]) -> list[TimeseriesPoint]:
    return [
        TimeseriesPoint(time=START + timedelta(hours=index), value=value)
        for index, value in enumerate(values)
    ]


class TestPvPowerStats:
    def test_one_day_profile(self):
        stats = spf_common_pv_power_stats_from_samples(hourly_samples(DAY_KW), "kW", 1.0)

        assert stats.sample_count == 9
        assert stats.energy_produced_kwh == pytest.approx(26.0)
        assert stats.energy_consumed_kwh == pytest.approx(0.1)  # two 0.05 kWh standby triangles
        assert (stats.peak_kw, stats.min_kw) == (10.0, -0.1)
        assert stats.average_kw == pytest.approx(25.9 / 8)  # net energy over the 8 h covered
        # producing intervals: 2-6, 6-10, 10-6, 6-2 kW (dawn 0-2 and dusk 2-0 are left out)
        assert stats.producing_hours == pytest.approx(4.0)
        assert stats.average_producing_kw == pytest.approx(24.0 / 4.0)
        assert stats.min_producing_kw == 2.0
        assert stats.producing_threshold_kw == 1.0

    def test_production_negative_meter_is_flipped(self):
        flipped = [-kw for kw in DAY_KW]
        stats = spf_common_pv_power_stats_from_samples(
            hourly_samples(flipped), "kW", 1.0, sign_convention="positive_is_consumption"
        )
        assert stats == spf_common_pv_power_stats_from_samples(hourly_samples(DAY_KW), "kW", 1.0)

    def test_watts_convert_to_kw(self):
        in_watts = [kw * 1000 for kw in DAY_KW]
        stats = spf_common_pv_power_stats_from_samples(hourly_samples(in_watts), "W", 1.0)
        assert (stats.peak_kw, stats.energy_produced_kwh) == (10.0, pytest.approx(26.0))

    def test_null_samples_are_skipped(self):
        stats = spf_common_pv_power_stats_from_samples(hourly_samples([4.0, None, 4.0]), "kW", 1.0)
        assert stats.sample_count == 2
        assert (stats.average_kw, stats.average_producing_kw) == (
            pytest.approx(4.0),
            pytest.approx(4.0),
        )

    def test_single_sample(self):
        stats = spf_common_pv_power_stats_from_samples(hourly_samples([5.0]), "kW", 1.0)
        assert (stats.peak_kw, stats.min_kw, stats.average_kw) == (5.0, 5.0, 5.0)
        assert (stats.producing_hours, stats.average_producing_kw, stats.min_producing_kw) == (
            0.0,
            None,
            5.0,
        )

    @pytest.mark.parametrize("values", [[], [None, None]])
    def test_no_values(self, values):
        stats = spf_common_pv_power_stats_from_samples(hourly_samples(values), "kW", 1.0)
        assert stats.sample_count == 0
        assert (stats.energy_produced_kwh, stats.energy_consumed_kwh, stats.producing_hours) == (
            0.0,
            0.0,
            0.0,
        )
        assert (stats.peak_kw, stats.average_kw, stats.min_kw) == (None, None, None)
        assert (stats.average_producing_kw, stats.min_producing_kw) == (None, None)

    def test_night_only_has_no_producing_figures(self):
        stats = spf_common_pv_power_stats_from_samples(hourly_samples([-0.1, -0.1, 0.0]), "kW", 1.0)
        assert stats.energy_produced_kwh == 0.0
        assert (stats.average_producing_kw, stats.min_producing_kw) == (None, None)

    @pytest.mark.parametrize("producing_threshold_kw", [0.0, -1.0])
    def test_threshold_must_be_positive(self, producing_threshold_kw):
        with pytest.raises(ValueError, match="producing_threshold_kw must be > 0"):
            spf_common_pv_power_stats_from_samples(
                hourly_samples(DAY_KW), "kW", producing_threshold_kw
            )

    def test_unknown_power_unit_is_an_error(self):
        with pytest.raises(ValueError, match="Unsupported power unit"):
            spf_common_pv_power_stats_from_samples(hourly_samples(DAY_KW), "kWh", 1.0)
