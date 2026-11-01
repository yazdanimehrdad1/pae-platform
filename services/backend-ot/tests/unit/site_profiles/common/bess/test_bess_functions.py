"""
Unit tests for the three-phase imbalance, energy and round trip efficiency functions in
site_profiles.common.bess.bess_functions.

Guards the wiring around the pure math: all points are read in one historian call, the result
names what it was computed from, and a misdeclared call (repeated point, points on two devices,
mixed or unsupported units, min_mean <= 0) is a SiteProfileConfigError instead of a wrong answer.
The historian read is faked at the module boundary. Round trip efficiency reads nothing: it is
given the site's sanitized series (kW discharge positive, SoC %), so its tests pass them in.
"""

from datetime import UTC, datetime, timedelta

import pytest

import site_profiles.common.bess.bess_functions as common_functions
from schemas.api_models import DevicePointResponse, PointTimeseries, TimeseriesPoint
from schemas.internal_models import TimestampedValue
from schemas.site_profiles import RoundTripEfficiencySettings, SiteContext, TimeWindow
from unit.site_fixtures import make_device, make_point, make_site
from utils.exceptions import SiteProfileConfigError

START = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
WINDOW = TimeWindow(start_time=START, end_time=START + timedelta(hours=1))


def phase_point(
    point_id: int, name: str, unit: str | None = "V", device_id: int = 3
) -> DevicePointResponse:
    return make_point(point_id, device_id, name).model_copy(update={"unit": unit})


VOLTAGE_POINTS = (
    phase_point(31, "poi_voltage_a"),
    phase_point(32, "poi_voltage_b"),
    phase_point(33, "poi_voltage_c"),
)


def context() -> SiteContext:
    return SiteContext(
        site=make_site(), devices=[make_device(3, list(VOLTAGE_POINTS), device_type="PV")]
    )


def fake_timeseries(
    monkeypatch: pytest.MonkeyPatch, values_by_point: dict[int, list[float]]
) -> list[list[int]]:
    """Serve one reading per value, 30 min apart, for each point; return the point ids of each read."""
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
                    TimeseriesPoint(time=START + timedelta(minutes=30) * index, value=value)
                    for index, value in enumerate(values_by_point[point.id])
                ],
                count=len(values_by_point[point.id]),  # as the real read sets it
            )
            for point in points
        }

    monkeypatch.setattr(common_functions, "spf_common_get_point_timeseries", get_point_timeseries)
    return reads


class TestPhaseImbalanceTimeseries:
    async def test_voltage_imbalance_per_timestamp(self, monkeypatch: pytest.MonkeyPatch):
        reads = fake_timeseries(
            monkeypatch, {31: [236.0, 230.0], 32: [228.0, 230.0], 33: [226.0, 0.0]}
        )

        result = await common_functions.spf_common_voltage_imbalance_timeseries(
            context(), VOLTAGE_POINTS, WINDOW, min_mean=10.0
        )

        assert reads == [[31, 32, 33]]  # one historian read for all three phases
        assert (result.quantity, result.device_id, result.unit, result.min_mean) == (
            "voltage",
            3,
            "V",
            10.0,
        )
        assert result.phase_point_ids == (31, 32, 33)
        assert [sample.imbalance_pct for sample in result.samples] == [
            pytest.approx(6 / 230 * 100),
            pytest.approx(100.0),  # lost phase C reads high, not None
        ]

    async def test_current_and_power_name_their_quantity(self, monkeypatch: pytest.MonkeyPatch):
        fake_timeseries(monkeypatch, {31: [0.1], 32: [-0.05], 33: [-0.04]})

        current = await common_functions.spf_common_current_imbalance_timeseries(
            context(), VOLTAGE_POINTS, WINDOW, min_mean=1.0
        )
        power = await common_functions.spf_common_power_imbalance_timeseries(
            context(), VOLTAGE_POINTS, WINDOW, min_mean=1.0
        )

        assert (current.quantity, power.quantity) == ("current", "power")
        (idle,) = power.samples
        assert (idle.status, idle.imbalance_pct, idle.spread) == (
            "below_threshold",
            None,
            pytest.approx(0.15),
        )

    @pytest.mark.parametrize(
        ("phase_points", "min_mean", "message"),
        [
            (
                (VOLTAGE_POINTS[0], VOLTAGE_POINTS[0], VOLTAGE_POINTS[2]),
                10.0,
                "three different points",
            ),
            (
                (
                    VOLTAGE_POINTS[0],
                    VOLTAGE_POINTS[1],
                    phase_point(13, "ac_voltage_l3_n", device_id=1),
                ),
                10.0,
                "one device",
            ),
            (
                (VOLTAGE_POINTS[0], VOLTAGE_POINTS[1], phase_point(33, "poi_voltage_c", unit="kV")),
                10.0,
                "one unit",
            ),
            (VOLTAGE_POINTS, 0.0, "min_mean must be > 0"),
        ],
    )
    async def test_misdeclared_call_is_a_config_error(
        self, monkeypatch: pytest.MonkeyPatch, phase_points, min_mean, message
    ):
        reads = fake_timeseries(monkeypatch, {})

        with pytest.raises(SiteProfileConfigError, match=message):
            await common_functions.spf_common_voltage_imbalance_timeseries(
                context(), phase_points, WINDOW, min_mean
            )
        assert reads == []  # rejected before touching the historian


RTE_SETTINGS = RoundTripEfficiencySettings(
    usable_energy_kwh=100.0, boundary="ac", min_charged_kwh=1.0, max_soc_change_pct=20.0
)


def hourly(values: list[float]) -> list[TimestampedValue]:
    return [
        TimestampedValue(time=START + timedelta(hours=index), value=value)
        for index, value in enumerate(values)
    ]


def charge_then_discharge_kw(discharge_kw: float) -> list[TimestampedValue]:
    """Hourly kW, discharge positive: 2 h at 40 kW in (80 kWh with the ramps), then out."""
    return hourly([0.0, -40.0, -40.0, 0.0, discharge_kw, discharge_kw, 0.0])


class TestBessRoundTripEfficiency:
    # the worked example, truly 90.25 %: 80 kWh in, and out 72.2 kWh (closed cycle)
    # or 62.7 kWh with 10 kWh still stored (SoC 50 -> 60 % of 100 kWh)
    @pytest.mark.parametrize(
        ("discharge_kw", "soc_end_pct", "discharged_kwh", "method"),
        [(36.1, 50.0, 72.2, "closed_cycle"), (31.35, 60.0, 62.7, "soc_corrected")],
    )
    def test_worked_example(self, discharge_kw, soc_end_pct, discharged_kwh, method):
        result = common_functions.spf_common_bess_round_trip_efficiency(
            charge_then_discharge_kw(discharge_kw), hourly([50.0, soc_end_pct]), RTE_SETTINGS
        )

        assert (result.boundary, result.status, result.method) == ("ac", "ok", method)
        assert (result.charged_kwh, result.discharged_kwh) == (
            pytest.approx(80.0),
            pytest.approx(discharged_kwh),
        )
        assert result.round_trip_efficiency_pct == pytest.approx(90.25)

    @pytest.mark.parametrize(
        ("soc_values", "settings_update", "status"),
        [
            ([50.0], {}, "missing_soc_data"),
            ([50.0, 50.0], {"min_charged_kwh": 500.0}, "insufficient_throughput"),
            ([20.0, 60.0], {}, "soc_change_too_large"),
        ],
    )
    def test_untrustworthy_windows_get_no_value(self, soc_values, settings_update, status):
        result = common_functions.spf_common_bess_round_trip_efficiency(
            charge_then_discharge_kw(36.1),
            hourly(soc_values),
            RTE_SETTINGS.model_copy(update=settings_update),
        )

        assert (result.status, result.round_trip_efficiency_pct) == (status, None)
        assert result.charged_kwh == pytest.approx(80.0)  # the measured terms are still reported

    def test_no_power_readings_is_insufficient_throughput(self):
        result = common_functions.spf_common_bess_round_trip_efficiency(
            [], hourly([50.0, 50.0]), RTE_SETTINGS
        )
        assert (result.status, result.charged_kwh, result.discharged_kwh) == (
            "insufficient_throughput",
            0.0,
            0.0,
        )


def in_window(
    values: list[TimestampedValue], start: datetime, end: datetime
) -> list[TimestampedValue]:
    return [value for value in values if start <= value.time <= end]


class TestBessRollingRoundTripEfficiency:
    # two worked-example cycles (closed, then ending 10 % fuller), back to back, with 30 min SoC
    POWER_KW = hourly(
        [0.0, -40.0, -40.0, 0.0, 36.1, 36.1, 0.0, -40.0, -40.0, 0.0, 31.35, 31.35, 0.0]
    )
    SOC_PCT = [
        TimestampedValue(
            time=START + timedelta(minutes=30 * index), value=50.0 + (index >= 14) * 10
        )
        for index in range(25)
    ]

    def rolling(
        self, lookback_hours: int = 6, settings: RoundTripEfficiencySettings = RTE_SETTINGS
    ):
        return common_functions.spf_common_bess_rolling_round_trip_efficiency(
            self.POWER_KW,
            self.SOC_PCT,
            settings,
            start_time=START,
            end_time=START + timedelta(hours=12),
            lookback=timedelta(hours=lookback_hours),
            step=timedelta(hours=1),
        )

    @pytest.mark.parametrize("lookback_hours", [1, 3, 6, 12])
    def test_each_value_is_the_round_trip_efficiency_of_its_window(self, lookback_hours):
        results = self.rolling(lookback_hours)

        assert [result.time for result in results] == [
            START + timedelta(hours=hours) for hours in range(13)
        ]
        for result in results:
            window_start = result.time - timedelta(hours=lookback_hours)
            expected = common_functions.spf_common_bess_round_trip_efficiency(
                in_window(self.POWER_KW, window_start, result.time),
                in_window(self.SOC_PCT, window_start, result.time),
                RTE_SETTINGS,
            )
            assert result.round_trip.status == expected.status
            assert result.round_trip.charged_kwh == pytest.approx(expected.charged_kwh)
            assert result.round_trip.discharged_kwh == pytest.approx(expected.discharged_kwh)
            assert result.round_trip.round_trip_efficiency_pct == (
                None
                if expected.round_trip_efficiency_pct is None
                else pytest.approx(expected.round_trip_efficiency_pct)
            )

    def test_each_full_cycle_is_the_worked_example(self):
        by_time = {result.time: result.round_trip for result in self.rolling()}

        closed = by_time[START + timedelta(hours=6)]
        corrected = by_time[START + timedelta(hours=12)]
        assert (closed.status, closed.method) == ("ok", "closed_cycle")
        assert (corrected.status, corrected.method) == ("ok", "soc_corrected")
        assert closed.round_trip_efficiency_pct == pytest.approx(90.25)
        assert corrected.round_trip_efficiency_pct == pytest.approx(90.25)

    def test_a_window_before_the_data_has_no_value(self):
        # the first hour's 6 h lookback has one power reading and one SoC reading
        first = self.rolling()[0].round_trip
        assert (first.status, first.charged_kwh, first.round_trip_efficiency_pct) == (
            "missing_soc_data",
            0.0,
            None,
        )

    def test_no_readings_give_missing_soc_data_every_hour(self):
        results = common_functions.spf_common_bess_rolling_round_trip_efficiency(
            [],
            [],
            RTE_SETTINGS,
            start_time=START,
            end_time=START + timedelta(hours=2),
            lookback=timedelta(hours=1),
            step=timedelta(hours=1),
        )
        assert [result.round_trip.status for result in results] == ["missing_soc_data"] * 3


INVERTER_POWER = phase_point(51, "active_power", unit="W", device_id=3)
OTHER_SITE_POWER = phase_point(52, "active_power", unit="kW", device_id=99)


class TestEnergyKwhByDevice:
    async def test_integrates_each_given_point(self, monkeypatch: pytest.MonkeyPatch):
        # 30 min steps: 2000 W for 1 h = 2 kWh
        reads = fake_timeseries(monkeypatch, {51: [2000.0, 2000.0, 2000.0]})

        result = await common_functions.spf_common_energy_kwh_by_device(
            context(), [INVERTER_POWER], WINDOW
        )

        assert reads == [[51]]
        (device,) = result.devices
        assert (device.device_id, device.device_name, device.point_id) == (3, "device_3", 51)
        assert (device.sample_count, device.energy_kwh) == (3, pytest.approx(2.0))
        assert result.energy_kwh == pytest.approx(2.0)

    async def test_no_points_is_zero(self, monkeypatch: pytest.MonkeyPatch):
        fake_timeseries(monkeypatch, {})
        result = await common_functions.spf_common_energy_kwh_by_device(context(), [], WINDOW)
        assert (result.devices, result.energy_kwh) == ([], 0.0)

    async def test_point_outside_the_site_is_a_config_error(self, monkeypatch: pytest.MonkeyPatch):
        reads = fake_timeseries(monkeypatch, {})
        with pytest.raises(SiteProfileConfigError, match="outside the site"):
            await common_functions.spf_common_energy_kwh_by_device(
                context(), [OTHER_SITE_POWER], WINDOW
            )
        assert reads == []

    async def test_non_power_unit_is_a_config_error(self, monkeypatch: pytest.MonkeyPatch):
        fake_timeseries(monkeypatch, {53: [1.0, 1.0]})
        energy_point = phase_point(53, "energy_total", unit="kWh", device_id=3)
        with pytest.raises(SiteProfileConfigError, match="can't be integrated"):
            await common_functions.spf_common_energy_kwh_by_device(
                context(), [energy_point], WINDOW
            )


class TestEnergyKwhSeriesByDevice:
    async def test_cumulative_kwh_at_each_power_samples_time(self, monkeypatch: pytest.MonkeyPatch):
        # 30 min steps: 2 kW, 2 kW, 4 kW
        reads = fake_timeseries(monkeypatch, {51: [2000.0, 2000.0, 4000.0]})

        result = await common_functions.spf_common_energy_kwh_series_by_device(
            context(), [INVERTER_POWER], WINDOW
        )

        assert reads == [[51]]
        total, device = result.series
        assert (total.id, total.name, total.unit) == (0, "site energy", "kWh")
        assert (device.id, device.name, device.count) == (51, "device_3 energy", 3)
        sample_times = [START + timedelta(minutes=30) * index for index in range(3)]
        assert [sample.time for sample in device.timeseries] == sample_times
        assert [sample.value for sample in device.timeseries] == pytest.approx([0.0, 1.0, 2.5])
        assert [sample.value for sample in total.timeseries] == pytest.approx([0.0, 1.0, 2.5])
        assert result.energy_kwh == pytest.approx(2.5)

    async def test_matches_the_energy_summary_total(self, monkeypatch: pytest.MonkeyPatch):
        values = {51: [2000.0, 500.0, 3500.0, 1200.0]}
        fake_timeseries(monkeypatch, values)
        series = await common_functions.spf_common_energy_kwh_series_by_device(
            context(), [INVERTER_POWER], WINDOW
        )
        summary = await common_functions.spf_common_energy_kwh_by_device(
            context(), [INVERTER_POWER], WINDOW
        )
        assert series.energy_kwh == pytest.approx(summary.energy_kwh)
        assert series.series[0].timeseries[-1].value == pytest.approx(summary.energy_kwh)

    async def test_site_total_sums_devices_per_poll_cycle(self, monkeypatch: pytest.MonkeyPatch):
        second_power = phase_point(61, "active_power", unit="kW", device_id=4)
        ctx = SiteContext(
            site=make_site(),
            devices=[
                make_device(3, [INVERTER_POWER], device_type="PV"),
                make_device(4, [second_power], device_type="BESS"),
            ],
        )
        fake_timeseries(monkeypatch, {51: [1000.0, 1000.0, 1000.0], 61: [3.0, 3.0, 3.0]})

        result = await common_functions.spf_common_energy_kwh_series_by_device(
            ctx, [INVERTER_POWER, second_power], WINDOW
        )

        total, *devices = result.series
        assert [series.name for series in devices] == ["device_3 energy", "device_4 energy"]
        assert [sample.value for sample in total.timeseries] == pytest.approx([0.0, 2.0, 4.0])
        assert result.energy_kwh == pytest.approx(4.0)

    async def test_no_points_gives_an_empty_site_total(self, monkeypatch: pytest.MonkeyPatch):
        fake_timeseries(monkeypatch, {})
        result = await common_functions.spf_common_energy_kwh_series_by_device(
            context(), [], WINDOW
        )
        (total,) = result.series
        assert (total.timeseries, result.energy_kwh) == ([], 0.0)

    async def test_point_outside_the_site_is_a_config_error(self, monkeypatch: pytest.MonkeyPatch):
        fake_timeseries(monkeypatch, {})
        with pytest.raises(SiteProfileConfigError, match="outside the site"):
            await common_functions.spf_common_energy_kwh_series_by_device(
                context(), [OTHER_SITE_POWER], WINDOW
            )

    async def test_non_power_unit_is_a_config_error(self, monkeypatch: pytest.MonkeyPatch):
        fake_timeseries(monkeypatch, {53: [1.0, 1.0]})
        energy_point = phase_point(53, "energy_total", unit="kWh", device_id=3)
        with pytest.raises(SiteProfileConfigError, match="can't be integrated"):
            await common_functions.spf_common_energy_kwh_series_by_device(
                context(), [energy_point], WINDOW
            )
