"""
Unit tests for site_profiles.individual_sites.powerflow_2bess_1pv.powerflow_2bess_1pv_alarms.

Guards each check of the site's alarms end to end over faked reads: the points it reads on the
devices the powerflow seed names, the bits decoded from each point's own labels, when it is active,
the value and device it reports, and that stale or missing readings never make it active.
Reads are faked at the module boundary.
"""

from datetime import UTC, datetime, timedelta

import pytest

import site_profiles.individual_sites.powerflow_2bess_1pv.powerflow_2bess_1pv_alarms as site_alarms
from helpers.virtual_points.resolve import input_max_gap
from schemas.api_models import DevicePointResponse
from schemas.internal_models import PointReading
from schemas.site_profiles import AlarmCheck, AlarmContext
from unit.site_fixtures import make_device, make_point, make_reading, make_site

NOW = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)
FRESH = NOW - timedelta(seconds=5)

INV_ST = {"0": "OFF", "3": "RUNNING", "4": "THROTTLED", "6": "FAULT"}
INVERTER_ALRM = {"2": "AC_DISCONNECT", "4": "GRID_DISCONNECT", "7": "OVER_TEMP", "12": "BLOWN_STRING_FUSE"}
EVT1 = {"0": "COMMUNICATION_ERROR", "1": "OVER_TEMP_ALARM", "2": "OVER_TEMP_WARNING", "14": "UNDER_SOC_MIN_WARNING", "21": "FAN_ERROR"}
THROT_SRC = {"0": "MAX_W", "1": "FIXED_W", "14": "DERATED"}
PPC_ALRM = {"0": "DEVICE_COMM_LOSS", "2": "POI_METER_FAIL"}
METER_EVT = {"2": "M_EVENT_Power_Failure", "3": "M_EVENT_Under_Voltage"}
METER_POINTS = {"PhVphAB": None, "PhVphBC": None, "PhVphCA": None, "Hz": None, "VA": None, "Evt": METER_EVT}

# The 2bess_1pv devices as the powerflow seed names them: id, name, points (name -> bit labels).
DEVICES: dict[str, tuple[int, dict[str, dict[str, str] | None]]] = {
    "2bess_1pv-plant_controller": (1, {"GridMode": None, "Alrm": PPC_ALRM}),
    "2bess_1pv-poi_meter": (2, METER_POINTS),
    "2bess_1pv-bess1": (3, {"InvSt": None, "Alrm": INVERTER_ALRM, "Evt1": EVT1, "SoC": None}),
    "2bess_1pv-bess2": (4, {"InvSt": None, "Alrm": INVERTER_ALRM, "Evt1": EVT1, "SoC": None}),
    "2bess_1pv-pv1": (5, {"InvSt": None, "Alrm": INVERTER_ALRM, "ThrotSrc": THROT_SRC, "W": None, "WAvail": None}),
    "2bess_1pv-m_bess1": (6, METER_POINTS),
    "2bess_1pv-m_bess2": (7, METER_POINTS),
    "2bess_1pv-m_pv1": (8, METER_POINTS),
}


def point_id(device: str, point: str) -> int:
    device_id, points = DEVICES[device]
    return device_id * 100 + list(points).index(point)


def context() -> AlarmContext:
    devices = []
    for name, (device_id, points) in DEVICES.items():
        device_points: list[DevicePointResponse] = [
            make_point(point_id(name, point), device_id, point).model_copy(update={"bitfield_detail": detail})
            for point, detail in points.items()
        ]
        devices.append(make_device(device_id, device_points).model_copy(update={"name": name}))
    return AlarmContext(site=make_site(profile="powerflow_2bess_1pv"), devices=devices, now=NOW)


def fake(
    monkeypatch: pytest.MonkeyPatch,
    values: dict[tuple[str, str], float],
    at: datetime = FRESH,
    last_polls: dict[int, datetime] | None = None,
) -> None:
    """Fake the latest readings, by (device, point) (others never reported), and the last polls."""
    by_id = {point_id(device, point): value for (device, point), value in values.items()}

    async def latest(point_ids: list[int], site_id: int | None = None) -> list[PointReading]:
        readings = [make_reading(pid, by_id.get(pid)) for pid in point_ids]
        return [r.model_copy(update={"timestamp": at}) if r.timestamp is not None else r for r in readings]

    async def polls(device_ids: list[int]) -> dict[int, datetime]:
        return {device_id: when for device_id, when in (last_polls or {}).items() if device_id in device_ids}

    monkeypatch.setattr(site_alarms, "get_latest_readings_by_point_ids", latest)
    monkeypatch.setattr(site_alarms, "get_last_successful_poll_times", polls)


def summary(check: AlarmCheck) -> tuple[bool, float | None, int | None]:
    return check.active, check.value, check.device_id


BESS1, PV1, PPC, POI = "2bess_1pv-bess1", "2bess_1pv-pv1", "2bess_1pv-plant_controller", "2bess_1pv-poi_meter"


class TestReadLatest:
    async def test_stale_reading_is_missing(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(BESS1, "InvSt"): 6.0}, at=NOW - input_max_gap() - timedelta(seconds=1))
        assert summary(await site_alarms.bess1_fault(context())) == (False, None, 3)

    async def test_point_the_site_lacks_is_missing(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {})
        latest = await site_alarms.read_latest(context(), [(BESS1, "NoSuchPoint"), ("no-device", "W")])
        assert latest == {}


class TestUnitFaults:
    async def test_bess_fault_state(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(BESS1, "InvSt"): 6.0, (BESS1, "Alrm"): 0.0, (BESS1, "Evt1"): 0.0})
        assert summary(await site_alarms.bess1_fault(context())) == (True, 6.0, 3)

    async def test_bess_battery_fault_bit_while_running(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(BESS1, "InvSt"): 3.0, (BESS1, "Evt1"): float(1 << 1)})  # OVER_TEMP_ALARM
        assert (await site_alarms.bess1_fault(context())).active

    async def test_bess_warning_and_grid_bits_are_not_a_fault(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(BESS1, "InvSt"): 3.0, (BESS1, "Alrm"): float(1 << 4), (BESS1, "Evt1"): float(1 << 2)})
        assert not (await site_alarms.bess1_fault(context())).active

    async def test_bess2_is_its_own_alarm(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(BESS1, "InvSt"): 6.0})
        assert summary(await site_alarms.bess2_fault(context())) == (False, None, 4)

    async def test_pv_breaker_open(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PV1, "InvSt"): 0.0, (PV1, "Alrm"): float(1 << 2)})  # AC_DISCONNECT
        assert summary(await site_alarms.pv1_fault(context())) == (True, 0.0, 5)


class TestPoiProblem:
    async def test_grid_lost_is_on_the_plant_controller(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PPC, "GridMode"): 3.0})  # BLACKOUT
        assert summary(await site_alarms.poi_problem(context())) == (True, 3.0, 1)

    async def test_meter_failure_is_on_the_poi_meter(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PPC, "GridMode"): 0.0, (PPC, "Alrm"): float(1 << 2)})
        assert summary(await site_alarms.poi_problem(context())) == (True, None, 2)

    async def test_meter_power_failure_event(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(POI, "Evt"): float(1 << 2)})
        assert (await site_alarms.poi_problem(context())).active

    async def test_grid_tied_and_healthy_is_not(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PPC, "GridMode"): 0.0, (PPC, "Alrm"): float(1 << 0), (POI, "Evt"): float(1 << 3)})
        assert summary(await site_alarms.poi_problem(context())) == (False, None, None)


class TestDeviceCommLoss:
    async def test_plant_controller_reports_it(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PPC, "Alrm"): float(1 << 0)}, last_polls={3: NOW})
        assert summary(await site_alarms.device_comm_loss(context())) == (True, 0, None)

    async def test_one_device_not_polled_is_on_that_device(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PPC, "Alrm"): 0.0}, last_polls={3: NOW - timedelta(seconds=61), 4: NOW})
        assert summary(await site_alarms.device_comm_loss(context())) == (True, 1, 3)

    async def test_several_devices_not_polled_is_site_level(self, monkeypatch: pytest.MonkeyPatch):
        old = NOW - timedelta(minutes=5)
        fake(monkeypatch, {}, last_polls={3: old, 4: old})
        assert summary(await site_alarms.device_comm_loss(context())) == (True, 2, None)

    async def test_all_polled_is_not(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PPC, "Alrm"): 0.0}, last_polls={3: NOW, 4: NOW})
        assert not (await site_alarms.device_comm_loss(context())).active


class TestPoiVoltageAndFrequency:
    @pytest.mark.parametrize(("kv", "out_of_range", "critical"), [
        (12.47, False, False), (13.0, False, False), (13.2, True, False), (11.5, True, False),
        (13.8, False, True), (11.0, False, True),
    ])
    async def test_bands(self, monkeypatch: pytest.MonkeyPatch, kv: float, out_of_range: bool, critical: bool):
        fake(monkeypatch, {(POI, "PhVphAB"): 12.47, (POI, "PhVphBC"): kv, (POI, "PhVphCA"): 12.47})
        warning = await site_alarms.poi_voltage_out_of_range(context())
        fault = await site_alarms.poi_voltage_critical(context())
        assert (warning.active, fault.active) == (out_of_range, critical)
        assert warning.value == pytest.approx((kv / 12.47 - 1) * 100) and warning.device_id == 2

    async def test_no_voltage_is_not_active(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {})
        assert summary(await site_alarms.poi_voltage_critical(context())) == (False, None, 2)

    async def test_frequency(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(POI, "Hz"): 59.2})
        assert summary(await site_alarms.poi_frequency_critical(context())) == (True, 59.2, 2)


class TestDerated:
    async def test_bess_warning_bit(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(BESS1, "Evt1"): float((1 << 2) | (1 << 21))})  # OVER_TEMP_WARNING, FAN_ERROR
        assert summary(await site_alarms.bess1_derated(context())) == (True, 2, 3)

    async def test_bess_soc_and_comms_warnings_dont_count(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(BESS1, "Evt1"): float((1 << 0) | (1 << 14))})
        assert not (await site_alarms.bess1_derated(context())).active

    async def test_pv_fuse(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PV1, "InvSt"): 3.0, (PV1, "Alrm"): float(1 << 12), (PV1, "ThrotSrc"): 0.0})
        assert summary(await site_alarms.pv1_derated(context())) == (True, 1, 5)

    async def test_pv_curtailed_is_not(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PV1, "InvSt"): 4.0, (PV1, "Alrm"): 0.0, (PV1, "ThrotSrc"): float(1 << 1)})
        assert not (await site_alarms.pv1_derated(context())).active


class TestBessSoc:
    async def test_lowest_below_the_band(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(BESS1, "SoC"): 40.0, ("2bess_1pv-bess2", "SoC"): 8.0})
        assert summary(await site_alarms.bess_soc_low(context())) == (True, 8.0, 4)
        assert summary(await site_alarms.bess_soc_high(context())) == (False, 40.0, 3)

    async def test_highest_above_the_band(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(BESS1, "SoC"): 91.0})
        assert summary(await site_alarms.bess_soc_high(context())) == (True, 91.0, 3)

    async def test_limits_themselves_are_fine(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(BESS1, "SoC"): 10.0, ("2bess_1pv-bess2", "SoC"): 90.0})
        assert not (await site_alarms.bess_soc_low(context())).active
        assert not (await site_alarms.bess_soc_high(context())).active

    async def test_no_soc_is_not_active(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {})
        assert summary(await site_alarms.bess_soc_low(context())) == (False, None, None)


class TestTransformerOverload:
    async def test_most_loaded_against_its_own_rating(self, monkeypatch: pytest.MonkeyPatch):
        # 3000 kVA overloads a BESS transformer (2750) but not the PV one (5500).
        fake(monkeypatch, {("2bess_1pv-m_bess2", "VA"): -3000.0, ("2bess_1pv-m_pv1", "VA"): 5000.0})
        assert summary(await site_alarms.transformer_overload(context())) == (
            True, pytest.approx(3000 / 2750 * 100), 7
        )

    async def test_within_rating_is_not(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {("2bess_1pv-m_pv1", "VA"): 5500.0})
        assert not (await site_alarms.transformer_overload(context())).active


class TestPvUnderperformance:
    async def test_running_unthrottled_below_80_pct(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PV1, "W"): 3000.0, (PV1, "WAvail"): 4000.0, (PV1, "ThrotSrc"): 0.0, (PV1, "InvSt"): 3.0})
        assert summary(await site_alarms.pv_underperformance(context())) == (True, 75.0, 5)

    async def test_throttled_is_not(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PV1, "W"): 3000.0, (PV1, "WAvail"): 4000.0, (PV1, "ThrotSrc"): 1.0, (PV1, "InvSt"): 3.0})
        assert not (await site_alarms.pv_underperformance(context())).active

    async def test_night_is_not(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {(PV1, "W"): 0.0, (PV1, "WAvail"): 10.0, (PV1, "ThrotSrc"): 0.0, (PV1, "InvSt"): 3.0})
        assert summary(await site_alarms.pv_underperformance(context())) == (False, None, 5)
