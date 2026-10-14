"""
Unit tests for site_profiles.common.bess.bess_helper_functions (the pure ones).

Guards the shared math: power units convert to kW (unknown units are an error, not a
silent 1:1), energy is the trapezoidal integral over time regardless of sample order,
and null samples are skipped rather than counted as zero. For round trip efficiency it
guards the formula on the worked example (true RTE 90.25 %, eta = 0.95 each way): exact for
a closed cycle and for a battery that ended fuller or emptier, where the plain ratio is
wrong; power split by sign at its zero crossings; counters summed through wraps and resets;
and the statuses that withhold a result.
"""

from datetime import UTC, datetime, timedelta

import pytest

from schemas.api_models import TimeseriesPoint
from schemas.site_profiles import RoundTripEfficiencySettings
from site_profiles.common.bess.bess_helper_functions import (
    _spf_common_first_and_last_value,
    _spf_common_phase_imbalance_pct,
    _spf_common_phase_imbalance_samples,
    _spf_common_round_trip_efficiency,
    _spf_common_stored_energy_change_kwh,
    spf_common_bess_power_stats_kw,
    spf_common_round_trip_efficiency_result,
)

START = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
SETTINGS = RoundTripEfficiencySettings(
    usable_energy_kwh=100.0, boundary="ac", min_charged_kwh=10.0, max_soc_change_pct=20.0
)


def samples(values: list[float | None], step: timedelta = timedelta(minutes=30)) -> list[TimeseriesPoint]:
    return [TimeseriesPoint(time=START + step * index, value=value) for index, value in enumerate(values)]


def hourly_samples(values: list[float | None]) -> list[TimeseriesPoint]:
    return samples(values, timedelta(hours=1))


class TestBessPowerStats:
    def test_signed_power_discharge_positive(self):
        # hourly 5 kW discharge, 8 kW charge, 2 kW discharge
        stats = spf_common_bess_power_stats_kw(samples([5.0, -8.0, 2.0], timedelta(hours=1)), "kW")
        assert stats.sample_count == 3
        assert stats.max_kw == 5.0
        assert stats.min_kw == -8.0
        assert stats.peak_kw == 8.0  # the charge is the largest magnitude
        assert stats.average_kw == pytest.approx(-2.25)  # (-1.5 kWh - 3 kWh) / 2 h

    def test_charge_positive_device_is_flipped(self):
        stats = spf_common_bess_power_stats_kw(
            samples([5.0, -8.0, 2.0], timedelta(hours=1)), "kW", sign_convention="positive_is_charge"
        )
        assert (stats.max_kw, stats.min_kw, stats.peak_kw) == (8.0, -5.0, 8.0)
        assert stats.average_kw == pytest.approx(2.25)

    def test_average_is_time_weighted(self):
        # 10 kW for 2 h, then a drop to 0 six minutes later: a plain mean would say 6.67 kW
        uneven = [
            TimeseriesPoint(time=START, value=10.0),
            TimeseriesPoint(time=START + timedelta(hours=2), value=10.0),
            TimeseriesPoint(time=START + timedelta(hours=2, minutes=6), value=0.0),
        ]
        assert spf_common_bess_power_stats_kw(uneven, "kW").average_kw == pytest.approx(20.5 / 2.1)

    def test_converts_to_kw_and_ignores_order(self):
        ordered = samples([1000.0, 3000.0], timedelta(hours=1))
        stats = spf_common_bess_power_stats_kw(list(reversed(ordered)), "W")
        assert (stats.max_kw, stats.min_kw, stats.peak_kw) == (3.0, 1.0, 3.0)
        assert stats.average_kw == pytest.approx(2.0)

    def test_null_samples_are_skipped(self):
        stats = spf_common_bess_power_stats_kw(samples([4.0, None, 4.0]), "kW")
        assert stats.sample_count == 2
        assert stats.average_kw == pytest.approx(4.0)

    def test_single_sample_average_is_its_value(self):
        stats = spf_common_bess_power_stats_kw(samples([-3.0]), "kW")
        assert (stats.max_kw, stats.min_kw, stats.peak_kw, stats.average_kw) == (-3.0, -3.0, 3.0, -3.0)

    @pytest.mark.parametrize("values", [[], [None, None]])
    def test_no_values_gives_none(self, values):
        stats = spf_common_bess_power_stats_kw(samples(values), "kW")
        assert stats.sample_count == 0
        assert (stats.peak_kw, stats.average_kw, stats.max_kw, stats.min_kw) == (None, None, None, None)

    def test_unknown_unit_is_an_error(self):
        with pytest.raises(ValueError, match="Unsupported power unit"):
            spf_common_bess_power_stats_kw(samples([1.0]), "kWh")


class TestPhaseImbalancePct:
    def test_balanced_is_zero(self):
        assert _spf_common_phase_imbalance_pct(230.0, 230.0, 230.0, min_mean=10.0) == 0.0

    def test_nema_max_deviation_over_mean(self):
        # mean 230, largest deviation 6 -> 2.61 %
        assert _spf_common_phase_imbalance_pct(236.0, 228.0, 226.0, min_mean=10.0) == pytest.approx(6 / 230 * 100)

    def test_lost_phase_reads_high_not_none(self):
        assert _spf_common_phase_imbalance_pct(230.0, 230.0, 0.0, min_mean=10.0) == pytest.approx(100.0)

    @pytest.mark.parametrize(
        "phases",
        [
            (0.0, 0.0, 0.0),  # dead bus
            (0.2, 0.1, 0.0),  # no load: a % would be 100
            (0.10, -0.05, -0.04),  # idle BESS: a % would be ~2,900
            (5.0, -5.0, 0.0),  # phases cancel: a % would divide by zero
        ],
    )
    def test_mean_below_threshold_is_none(self, phases):
        assert _spf_common_phase_imbalance_pct(*phases, min_mean=1.0) is None

    def test_signed_power_uses_absolute_mean(self):
        # net charging: mean -10 kW, largest deviation 2 -> 20 %
        assert _spf_common_phase_imbalance_pct(-12.0, -10.0, -8.0, min_mean=1.0) == pytest.approx(20.0)

    @pytest.mark.parametrize("min_mean", [0.0, -1.0])
    def test_min_mean_must_be_positive(self, min_mean):
        with pytest.raises(ValueError, match="min_mean must be > 0"):
            _spf_common_phase_imbalance_pct(1.0, 1.0, 1.0, min_mean=min_mean)


class TestPhaseImbalanceSamples:
    def test_one_sample_per_shared_timestamp(self):
        imbalance = _spf_common_phase_imbalance_samples(
            samples([236.0, 0.0]), samples([228.0, 0.0]), samples([226.0, 0.0]), min_mean=10.0
        )
        assert [sample.time for sample in imbalance] == [START, START + timedelta(minutes=30)]
        first, dead_bus = imbalance
        assert (first.phase_a, first.phase_b, first.phase_c) == (236.0, 228.0, 226.0)
        assert first.mean == pytest.approx(230.0)
        assert first.spread == pytest.approx(10.0)
        assert first.imbalance_pct == pytest.approx(6 / 230 * 100)
        assert first.status == "ok"
        assert (dead_bus.imbalance_pct, dead_bus.status, dead_bus.spread) == (None, "below_threshold", 0.0)

    def test_timestamp_missing_or_null_on_any_phase_is_skipped(self):
        phase_a = samples([230.0, 230.0, 230.0])
        phase_b = samples([230.0, None, 230.0])
        phase_c = samples([230.0, 230.0])  # no third reading
        imbalance = _spf_common_phase_imbalance_samples(phase_a, phase_b, phase_c, min_mean=10.0)
        assert [sample.time for sample in imbalance] == [START]

    def test_oldest_first_whatever_the_input_order(self):
        imbalance = _spf_common_phase_imbalance_samples(
            list(reversed(samples([1.0, 2.0, 3.0]))), samples([1.0, 2.0, 3.0]), samples([1.0, 2.0, 3.0]), min_mean=0.5
        )
        assert [sample.mean for sample in imbalance] == [1.0, 2.0, 3.0]

    def test_no_samples_is_empty(self):
        assert _spf_common_phase_imbalance_samples([], [], [], min_mean=1.0) == []


class TestRoundTripEfficiencyFormula:
    # (E_ch, E_dis, Delta S): closed cycle, ended fuller, ended emptier; all truly 90.25 %
    @pytest.mark.parametrize(
        ("charged_kwh", "discharged_kwh", "stored_energy_change_kwh"),
        [(80.0, 72.2, 0.0), (80.0, 62.7, 10.0), (80.0, 81.7, -10.0)],
    )
    def test_worked_example_is_exact(self, charged_kwh, discharged_kwh, stored_energy_change_kwh):
        assert _spf_common_round_trip_efficiency(
            charged_kwh, discharged_kwh, stored_energy_change_kwh
        ) == pytest.approx(0.9025)

    def test_closed_cycle_is_the_plain_ratio(self):
        assert _spf_common_round_trip_efficiency(50.0, 43.0, 0.0) == pytest.approx(43.0 / 50.0)

    def test_no_charged_energy_is_an_error(self):
        with pytest.raises(ValueError, match="charged_kwh must be > 0"):
            _spf_common_round_trip_efficiency(0.0, 5.0, 0.0)

    def test_stored_energy_change(self):
        assert _spf_common_stored_energy_change_kwh(50.0, 60.0, 100.0) == pytest.approx(10.0)
        assert _spf_common_stored_energy_change_kwh(50.0, 40.0, 200.0) == pytest.approx(-20.0)


class TestFirstAndLastValue:
    def test_oldest_and_newest_whatever_the_order(self):
        assert _spf_common_first_and_last_value(list(reversed(hourly_samples([50.0, None, 60.0])))) == (
            50.0,
            60.0,
        )

    @pytest.mark.parametrize("values", [[], [50.0], [None, 50.0]])
    def test_fewer_than_two_is_none(self, values):
        assert _spf_common_first_and_last_value(hourly_samples(values)) is None


class TestRoundTripEfficiencyResult:
    def result(
        self, soc_values, charged_kwh=80.0, discharged_kwh=62.7, aux_kwh=None, settings=SETTINGS
    ):
        return spf_common_round_trip_efficiency_result(
            boundary=settings.boundary,
            energy_source="counters",
            charged_kwh=charged_kwh,
            discharged_kwh=discharged_kwh,
            aux_kwh=aux_kwh,
            soc_samples=hourly_samples(soc_values),
            settings=settings,
        )

    def test_soc_corrected_result(self):
        result = self.result([50.0, 55.0, 60.0])
        assert (result.status, result.method) == ("ok", "soc_corrected")
        assert result.round_trip_efficiency_pct == pytest.approx(90.25)
        assert (result.soc_start_pct, result.soc_end_pct) == (50.0, 60.0)
        assert result.stored_energy_change_kwh == pytest.approx(10.0)

    def test_closed_cycle_result(self):
        result = self.result([50.0, 50.0], discharged_kwh=72.2)
        assert (result.status, result.method) == ("ok", "closed_cycle")
        assert result.round_trip_efficiency_pct == pytest.approx(90.25)

    def test_aux_energy_counts_as_energy_in(self):
        system = SETTINGS.model_copy(update={"boundary": "system"})
        result = self.result(
            [50.0, 50.0], charged_kwh=76.0, discharged_kwh=72.2, aux_kwh=4.0, settings=system
        )
        assert result.round_trip_efficiency_pct == pytest.approx(72.2 / 80.0 * 100)

    @pytest.mark.parametrize(
        ("soc_values", "charged_kwh", "status"),
        [
            ([50.0], 80.0, "missing_soc_data"),
            ([50.0, 50.0], 5.0, "insufficient_throughput"),
            ([20.0, 60.0], 80.0, "soc_change_too_large"),
        ],
    )
    def test_untrustworthy_windows_get_no_value(self, soc_values, charged_kwh, status):
        result = self.result(soc_values, charged_kwh=charged_kwh)
        assert (result.status, result.round_trip_efficiency_pct, result.method) == (
            status,
            None,
            None,
        )
        assert result.charged_kwh == charged_kwh  # the measured terms are still reported

    def test_above_100_percent_is_reported_and_flagged(self):
        result = self.result([50.0, 50.0], discharged_kwh=90.0)
        assert result.status == "above_100_percent"
        assert result.round_trip_efficiency_pct == pytest.approx(112.5)

    @pytest.mark.parametrize(
        "update",
        [{"usable_energy_kwh": 0.0}, {"min_charged_kwh": -1.0}, {"max_soc_change_pct": 120.0}],
    )
    def test_invalid_settings_are_rejected(self, update):
        with pytest.raises(ValueError):
            RoundTripEfficiencySettings(**(SETTINGS.model_dump() | update))
