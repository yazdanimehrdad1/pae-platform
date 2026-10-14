"""
Unit tests for site_profiles.common.shared_helper_functions (the pure ones).

Guards the shared math: power units convert to kW and energy units to kWh (unknown units are
an error, not a silent 1:1), energy is the trapezoidal integral over time regardless of sample
order, power splits by sign at its zero crossings, counters are summed over their increases
through wraps and resets, and null samples are skipped rather than counted as zero. Series keep
their samples' own times: cumulative energy has one value per power sample and ends at the
whole-window integral, and combined series give one sample per poll cycle across devices.
"""

from datetime import UTC, datetime, timedelta

import pytest

from schemas.api_models import TimeseriesPoint
from site_profiles.common.shared_helper_functions import (
    _spf_common_energy_unit_to_kwh_factor,
    spf_common_combine_series,
    spf_common_counter_energy_kwh,
    spf_common_cumulative_energy_kwh,
    spf_common_integrate_power_to_energy_kwh,
    spf_common_mean_sample_value,
    spf_common_power_unit_to_kw_factor,
    spf_common_split_power_by_sign_kwh,
)

START = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def samples(
    values: list[float | None], step: timedelta = timedelta(minutes=30)
) -> list[TimeseriesPoint]:
    return [
        TimeseriesPoint(time=START + step * index, value=value)
        for index, value in enumerate(values)
    ]


def hourly_samples(values: list[float | None]) -> list[TimeseriesPoint]:
    return samples(values, timedelta(hours=1))


class TestPowerToKwFactor:
    @pytest.mark.parametrize(("unit", "factor"), [("W", 0.001), ("kW", 1.0), ("MW", 1000.0)])
    def test_known_units(self, unit, factor):
        assert spf_common_power_unit_to_kw_factor(unit) == factor

    @pytest.mark.parametrize("unit", ["kWh", "w", None])
    def test_unknown_unit_is_an_error(self, unit):
        with pytest.raises(ValueError, match="Unsupported power unit"):
            spf_common_power_unit_to_kw_factor(unit)


class TestEnergyKwh:
    def test_constant_power_for_one_hour(self):
        assert spf_common_integrate_power_to_energy_kwh(
            samples([1000.0, 1000.0, 1000.0]), "W"
        ) == pytest.approx(1.0)

    def test_ramp_uses_trapezoids(self):
        # 0 -> 2 kW over 1 h is 1 kWh
        assert spf_common_integrate_power_to_energy_kwh(
            samples([0.0, 2.0], timedelta(hours=1)), "kW"
        ) == pytest.approx(1.0)

    def test_sample_order_does_not_matter(self):
        ordered = samples([0.0, 2.0, 4.0], timedelta(hours=1))
        assert spf_common_integrate_power_to_energy_kwh(
            list(reversed(ordered)), "kW"
        ) == pytest.approx(spf_common_integrate_power_to_energy_kwh(ordered, "kW"))

    def test_null_samples_are_skipped(self):
        assert spf_common_integrate_power_to_energy_kwh(
            samples([1.0, None, 1.0]), "kW"
        ) == pytest.approx(1.0)

    @pytest.mark.parametrize("values", [[], [5.0], [None, None]])
    def test_fewer_than_two_samples_is_zero(self, values):
        assert spf_common_integrate_power_to_energy_kwh(samples(values), "kW") == 0.0


class TestAverage:
    def test_mean_of_non_null_values(self):
        assert spf_common_mean_sample_value(samples([1.0, None, 3.0])) == 2.0

    def test_no_values_is_none(self):
        assert spf_common_mean_sample_value(samples([None])) is None
        assert spf_common_mean_sample_value([]) is None


class TestSplitPowerBySign:
    def test_each_sign_integrated_and_zero_crossing_split(self):
        # -10 -> -10 kW: 10 kWh negative; -10 -> +10: 2.5 each side; +10 -> +10: 10 kWh positive
        positive_kwh, negative_kwh = spf_common_split_power_by_sign_kwh(
            hourly_samples([-10.0, -10.0, 10.0, 10.0]), "kW"
        )
        assert (positive_kwh, negative_kwh) == (pytest.approx(12.5), pytest.approx(12.5))

    def test_unequal_crossing_and_unit_conversion(self):
        # 3000 W -> -1000 W over 1 h crosses 0 at 3/4 h: 1.125 kWh positive, 0.125 kWh negative
        positive_kwh, negative_kwh = spf_common_split_power_by_sign_kwh(
            hourly_samples([3000.0, -1000.0]), "W"
        )
        assert (positive_kwh, negative_kwh) == (pytest.approx(1.125), pytest.approx(0.125))

    def test_unknown_power_unit_is_an_error(self):
        with pytest.raises(ValueError, match="Unsupported power unit"):
            spf_common_split_power_by_sign_kwh(hourly_samples([1.0]), "kWh")


class TestCounterEnergy:
    def test_sum_of_increases_in_kwh(self):
        assert spf_common_counter_energy_kwh(
            hourly_samples([100.0, 150.0, None, 200.0]), "Wh", None
        ) == pytest.approx(0.1)

    def test_wrap_near_the_top_carries_on_from_zero(self):
        # 900 -> 950 (+50), wraps at 1000 -> 50 (+100)
        assert spf_common_counter_energy_kwh(
            hourly_samples([900.0, 950.0, 50.0]), "kWh", 1000.0
        ) == pytest.approx(150.0)

    @pytest.mark.parametrize(
        ("values", "counter_rollover"),
        [
            ([900.0, 950.0, 10.0, 60.0], None),  # no rollover declared: a drop is a reset
            (
                [100.0, 150.0, 10.0, 60.0],
                1000.0,
            ),  # dropped from the bottom half: a reset, not a wrap
        ],
    )
    def test_reset_counts_zero_then_resumes(self, values, counter_rollover):
        assert spf_common_counter_energy_kwh(
            hourly_samples(values), "kWh", counter_rollover
        ) == pytest.approx(100.0)

    def test_unknown_energy_unit_is_an_error(self):
        with pytest.raises(ValueError, match="Unsupported energy unit"):
            _spf_common_energy_unit_to_kwh_factor("kW")


class TestCumulativeEnergyKwh:
    def test_running_total_at_each_samples_own_time(self):
        cumulative = spf_common_cumulative_energy_kwh(samples([2.0, 2.0, 4.0]), "kW")
        assert [sample.time for sample in cumulative] == [START + timedelta(minutes=30) * index for index in range(3)]
        # 2 kW for 30 min = 1 kWh; the 2 -> 4 kW ramp for 30 min = 1.5 kWh
        assert [sample.value for sample in cumulative] == pytest.approx([0.0, 1.0, 2.5])

    def test_last_value_is_the_whole_window_integral(self):
        values = [0.0, 1500.0, -800.0, None, 3000.0, 2500.0, 100.0]
        cumulative = spf_common_cumulative_energy_kwh(samples(values), "W")
        assert cumulative[-1].value == pytest.approx(spf_common_integrate_power_to_energy_kwh(samples(values), "W"))

    def test_null_samples_are_skipped_and_order_does_not_matter(self):
        shuffled = list(reversed(samples([1.0, None, 1.0])))
        cumulative = spf_common_cumulative_energy_kwh(shuffled, "kW")
        assert [sample.value for sample in cumulative] == pytest.approx([0.0, 1.0])

    def test_no_samples_is_an_empty_series(self):
        assert spf_common_cumulative_energy_kwh([], "kW") == []

    def test_non_power_unit_is_an_error(self):
        with pytest.raises(ValueError, match="Unsupported power unit"):
            spf_common_cumulative_energy_kwh(samples([1.0, 1.0]), "kWh")


def offset(seconds: float, value: float | None) -> TimeseriesPoint:
    return TimeseriesPoint(time=START + timedelta(seconds=seconds), value=value)


class TestCombineSeries:
    GAP = timedelta(seconds=30)

    def test_one_sample_per_poll_cycle_at_the_devices_own_times(self):
        # device 2 is polled 0.3 s after device 1 in each 10 s cycle
        first = [offset(0, 1.0), offset(10, 2.0)]
        second = [offset(0.3, 10.0), offset(10.3, 20.0)]
        combined = spf_common_combine_series([first, second], sum, self.GAP)
        assert [((sample.time - START).total_seconds(), sample.value) for sample in combined] == [(0.3, 11.0), (10.3, 22.0)]

    def test_a_series_with_nothing_recent_leaves_a_gap(self):
        first = [offset(0, 1.0), offset(60, 2.0)]
        second = [offset(0, 10.0)]
        combined = spf_common_combine_series([first, second], sum, self.GAP)
        assert [(sample.time - START).total_seconds() for sample in combined] == [0.0]

    def test_null_samples_are_skipped(self):
        combined = spf_common_combine_series([[offset(0, 1.0), offset(10, None)]], sum, self.GAP)
        assert [sample.value for sample in combined] == [1.0]

    def test_an_empty_series_gives_nothing(self):
        assert spf_common_combine_series([[offset(0, 1.0)], []], sum, self.GAP) == []
        assert spf_common_combine_series([], sum, self.GAP) == []
