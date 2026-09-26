"""
Unit tests for site_profiles.common.calculations.

Guards the shared math: power units convert to kW (unknown units are an error, not a
silent 1:1), energy is the trapezoidal integral over time regardless of sample order,
and null samples are skipped rather than counted as zero.
"""

from datetime import UTC, datetime, timedelta

import pytest

from schemas.api_models import TimeseriesPoint
from site_profiles.common.calculations import average, energy_kwh, power_to_kw_factor

START = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def samples(values: list[float | None], step: timedelta = timedelta(minutes=30)) -> list[TimeseriesPoint]:
    return [TimeseriesPoint(time=START + step * index, value=value) for index, value in enumerate(values)]


class TestPowerToKwFactor:
    @pytest.mark.parametrize(("unit", "factor"), [("W", 0.001), ("kW", 1.0), ("MW", 1000.0)])
    def test_known_units(self, unit, factor):
        assert power_to_kw_factor(unit) == factor

    @pytest.mark.parametrize("unit", ["kWh", "w", None])
    def test_unknown_unit_is_an_error(self, unit):
        with pytest.raises(ValueError, match="Unsupported power unit"):
            power_to_kw_factor(unit)


class TestEnergyKwh:
    def test_constant_power_for_one_hour(self):
        assert energy_kwh(samples([1000.0, 1000.0, 1000.0]), "W") == pytest.approx(1.0)

    def test_ramp_uses_trapezoids(self):
        # 0 -> 2 kW over 1 h is 1 kWh
        assert energy_kwh(samples([0.0, 2.0], timedelta(hours=1)), "kW") == pytest.approx(1.0)

    def test_sample_order_does_not_matter(self):
        ordered = samples([0.0, 2.0, 4.0], timedelta(hours=1))
        assert energy_kwh(list(reversed(ordered)), "kW") == pytest.approx(energy_kwh(ordered, "kW"))

    def test_null_samples_are_skipped(self):
        assert energy_kwh(samples([1.0, None, 1.0]), "kW") == pytest.approx(1.0)

    @pytest.mark.parametrize("values", [[], [5.0], [None, None]])
    def test_fewer_than_two_samples_is_zero(self, values):
        assert energy_kwh(samples(values), "kW") == 0.0


class TestAverage:
    def test_mean_of_non_null_values(self):
        assert average(samples([1.0, None, 3.0])) == 2.0

    def test_no_values_is_none(self):
        assert average(samples([None])) is None
        assert average([]) is None
