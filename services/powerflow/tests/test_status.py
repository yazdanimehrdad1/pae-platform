"""Status enums and alarm bitfields: derivation rules, and that they reach the snapshot."""

import asyncio

import pytest
from conftest import PROFILES, site_config_dict

from powerflow.core.engine import Engine
from powerflow.core.runtime import SiteRuntime
from powerflow.models.bess import BessFlag, BessMode, BessOutput, BessSetpoint, BessStatus
from powerflow.models.pv import PvFlag, PvOutput, PvStatus
from powerflow.models.status import (
    BessAlarm,
    BessOperatingState,
    MeterAlarm,
    PvAlarm,
    PvInverterState,
    SiteAlarm,
    bess_alarms,
    bess_operating_state,
    load_alarms,
    meter_alarms,
    pv_alarms,
    pv_inverter_state,
    site_alarms,
)
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.site_config import SiteConfig


def bess_output(p_kw: float, status: BessStatus) -> BessOutput:
    return BessOutput(p_kw, 0, p_kw, 0, BessFlag.NONE, status, 0)


@pytest.mark.parametrize(
    ("p_kw", "status", "expected"),
    [
        (500, BessStatus.RUNNING, BessOperatingState.DISCHARGING),
        (-500, BessStatus.RUNNING, BessOperatingState.CHARGING),
        (0, BessStatus.IDLE, BessOperatingState.STANDBY),
        (0, BessStatus.OFFLINE, BessOperatingState.OFF),
        (0, BessStatus.FAULT, BessOperatingState.FAULT),
    ],
)
def test_bess_operating_state(
    p_kw: float, status: BessStatus, expected: BessOperatingState
) -> None:
    assert bess_operating_state(bess_output(p_kw, status)) is expected


def test_bess_alarms() -> None:
    assert bess_alarms(50, 5, 95, 1.0, 50) == BessAlarm.NONE
    assert bess_alarms(9, 5, 95, 1.0, 50) == BessAlarm.SOC_LOW_WARNING
    assert bess_alarms(91, 5, 95, 1.0, 50) == BessAlarm.SOC_HIGH_WARNING
    assert bess_alarms(50, 5, 95, 0.94, 50) == BessAlarm.UNDERVOLTAGE
    assert (
        bess_alarms(50, 5, 95, 1.06, 120) == BessAlarm.OVERVOLTAGE | BessAlarm.TRANSFORMER_OVERLOAD
    )
    assert bess_alarms(50, 5, 95, 0.0, 0) == BessAlarm.NONE  # no network yet: no voltage alarm


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (PvStatus.OFF, PvInverterState.SLEEPING),
        (PvStatus.PRODUCING, PvInverterState.MPPT),
        (PvStatus.CURTAILED, PvInverterState.THROTTLED),
        (PvStatus.OFFLINE, PvInverterState.OFF),
    ],
)
def test_pv_inverter_state(status: PvStatus, expected: PvInverterState) -> None:
    output = PvOutput(0, 0, 0, 0, PvFlag.NONE, status, 0)
    assert pv_inverter_state(output) is expected


def test_pv_load_meter_and_site_alarms() -> None:
    assert pv_alarms(1.07, 101) == PvAlarm.OVERVOLTAGE | PvAlarm.TRANSFORMER_OVERLOAD
    assert load_alarms(0.9).name == "UNDERVOLTAGE"
    assert meter_alarms(2000, 1.0, 0.99, 2020) == MeterAlarm.EXPORTING
    assert meter_alarms(-2000, 1.0, 0.8, 2500) == MeterAlarm.IMPORTING | MeterAlarm.LOW_POWER_FACTOR
    assert meter_alarms(0.5, 1.0, 0.1, 0.5) == MeterAlarm.NONE  # idle POI: no direction, no pf
    assert site_alarms(False, 3, True) == (
        SiteAlarm.NOT_CONVERGED | SiteAlarm.OVERRUN | SiteAlarm.TEST_MODE
    )
    assert site_alarms(None, 0, False) == SiteAlarm.NONE


def test_status_words_in_the_snapshot() -> None:
    config = SiteConfig.model_validate(site_config_dict(n_bess=1, n_pv=1))
    engine = Engine(
        SiteRuntime.build(config, PROFILES, PandapowerSolver), PandapowerSolver, PROFILES
    )
    engine.setpoints.set_bess("bess1", BessSetpoint(-800, 0, BessMode.PQ))
    snapshot = asyncio.run(engine.step(2))
    bess = snapshot.bess[0]
    assert bess.operating_state_name == "CHARGING"
    assert bess.alarm_flag_names == []
    assert snapshot.pv[0].inverter_state_name == "MPPT"  # noon, full sun
    assert snapshot.loads[0].supply_state_name == "ENERGIZED"
    assert snapshot.poi.meter_state_name == "OK"
    # Exporting ~540 kW while drawing ~480 kvar: |pf| ≈ 0.74 also raises LOW_POWER_FACTOR.
    assert snapshot.poi.alarm_flag_names == ["EXPORTING", "LOW_POWER_FACTOR"]
