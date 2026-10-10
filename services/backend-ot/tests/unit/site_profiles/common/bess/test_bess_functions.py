"""
Unit tests for the three-phase imbalance and round trip efficiency functions in
site_profiles.common.bess.bess_functions.

Guards the wiring around the pure math: all points are read in one historian call, the result
names what it was computed from, and a misdeclared call (repeated point, points on two devices,
mixed or unsupported units, min_mean <= 0, an aux counter outside the system boundary) is a
SiteProfileConfigError instead of a wrong answer. The historian read is faked at the module
boundary.
"""

from datetime import UTC, datetime, timedelta

import pytest

import site_profiles.common.bess.bess_functions as common_functions
from schemas.api_models import DevicePointResponse, PointTimeseries, TimeseriesPoint
from schemas.site_profiles import (
    RoundTripCounterSource,
    RoundTripEfficiencySettings,
    RoundTripPowerSource,
    SiteContext,
    TimeWindow,
)
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


POWER_POINT = phase_point(41, "bess_active_power", unit="kW")
CHARGED_POINT = phase_point(42, "energy_charged", unit="kWh")
DISCHARGED_POINT = phase_point(43, "energy_discharged", unit="kWh")
SOC_POINT = phase_point(44, "state_of_charge", unit="%")
AUX_POINT = phase_point(45, "aux_energy", unit="kWh")
COUNTERS = RoundTripCounterSource(
    charged_counter_point=CHARGED_POINT, discharged_counter_point=DISCHARGED_POINT
)
RTE_SETTINGS = RoundTripEfficiencySettings(
    usable_energy_kwh=100.0, boundary="ac", min_charged_kwh=1.0, max_soc_change_pct=20.0
)


class TestBessRoundTripEfficiency:
    async def test_counters_with_soc_correction(self, monkeypatch: pytest.MonkeyPatch):
        # the worked example: ended 10 % fuller, truly 90.25 %
        reads = fake_timeseries(monkeypatch, {42: [0.0, 80.0], 43: [0.0, 62.7], 44: [50.0, 60.0]})

        result = await common_functions.spf_common_bess_round_trip_efficiency(
            context(), COUNTERS, SOC_POINT, WINDOW, RTE_SETTINGS
        )

        assert reads == [[42, 43, 44]]  # one historian read for every point
        assert (result.energy_source, result.boundary, result.status) == ("counters", "ac", "ok")
        assert result.round_trip_efficiency_pct == pytest.approx(90.25)

    async def test_power_source_is_split_by_sign(self, monkeypatch: pytest.MonkeyPatch):
        # 30 min steps: -10, -10, +10, +10 kW -> 6.25 kWh in and 6.25 kWh out
        fake_timeseries(monkeypatch, {41: [-10.0, -10.0, 10.0, 10.0], 44: [50.0, 50.0]})

        result = await common_functions.spf_common_bess_round_trip_efficiency(
            context(),
            RoundTripPowerSource(power_point=POWER_POINT),
            SOC_POINT,
            WINDOW,
            RTE_SETTINGS,
        )

        assert result.energy_source == "power"
        assert (result.charged_kwh, result.discharged_kwh) == (
            pytest.approx(6.25),
            pytest.approx(6.25),
        )
        assert (result.method, result.round_trip_efficiency_pct) == (
            "closed_cycle",
            pytest.approx(100.0),
        )

    @pytest.mark.parametrize(
        ("sign_convention", "expected_charged_kwh", "expected_discharged_kwh"),
        [("positive_is_discharge", 16 / 3, 7 / 3), ("positive_is_charge", 7 / 3, 16 / 3)],
    )
    async def test_sign_convention_maps_signs_to_charge_and_discharge(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sign_convention,
        expected_charged_kwh,
        expected_discharged_kwh,
    ):
        # 30 min steps: -8, -8, +4, +4 kW -> 16/3 kWh negative, 7/3 kWh positive
        fake_timeseries(monkeypatch, {41: [-8.0, -8.0, 4.0, 4.0], 44: [50.0, 50.0]})
        power_source = RoundTripPowerSource(
            power_point=POWER_POINT, sign_convention=sign_convention
        )

        result = await common_functions.spf_common_bess_round_trip_efficiency(
            context(), power_source, SOC_POINT, WINDOW, RTE_SETTINGS
        )

        assert result.charged_kwh == pytest.approx(expected_charged_kwh)
        assert result.discharged_kwh == pytest.approx(expected_discharged_kwh)

    async def test_aux_counter_is_read_for_the_system_boundary(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        reads = fake_timeseries(
            monkeypatch, {42: [0.0, 76.0], 43: [0.0, 72.2], 44: [50.0, 50.0], 45: [10.0, 14.0]}
        )
        system = RTE_SETTINGS.model_copy(update={"boundary": "system"})

        result = await common_functions.spf_common_bess_round_trip_efficiency(
            context(), COUNTERS, SOC_POINT, WINDOW, system, aux_counter_point=AUX_POINT
        )

        assert reads == [[42, 43, 44, 45]]
        assert result.aux_kwh == pytest.approx(4.0)
        assert result.round_trip_efficiency_pct == pytest.approx(72.2 / 80.0 * 100)

    @pytest.mark.parametrize(
        ("energy_source", "soc_point", "aux_counter_point", "message"),
        [
            (COUNTERS, SOC_POINT, AUX_POINT, "only applies to boundary 'system'"),
            (COUNTERS, CHARGED_POINT, None, "each point may be used once"),
        ],
    )
    async def test_misdeclared_call_is_a_config_error_before_reading(
        self, monkeypatch: pytest.MonkeyPatch, energy_source, soc_point, aux_counter_point, message
    ):
        reads = fake_timeseries(monkeypatch, {})

        with pytest.raises(SiteProfileConfigError, match=message):
            await common_functions.spf_common_bess_round_trip_efficiency(
                context(),
                energy_source,
                soc_point,
                WINDOW,
                RTE_SETTINGS,
                aux_counter_point=aux_counter_point,
            )
        assert reads == []

    async def test_unsupported_unit_is_a_config_error(self, monkeypatch: pytest.MonkeyPatch):
        fake_timeseries(monkeypatch, {41: [1.0, 1.0], 44: [50.0, 50.0]})
        energy_point = POWER_POINT.model_copy(
            update={"unit": "kWh"}
        )  # an energy unit on a power point

        with pytest.raises(SiteProfileConfigError, match="Unsupported power unit"):
            await common_functions.spf_common_bess_round_trip_efficiency(
                context(),
                RoundTripPowerSource(power_point=energy_point),
                SOC_POINT,
                WINDOW,
                RTE_SETTINGS,
            )


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
