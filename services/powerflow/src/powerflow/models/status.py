"""Device-style status words: a 16-bit state enum and a 16-bit alarm bitfield per asset type,
derived each step from the simulated values. Pure Python.

Fault, cause and comm-loss bits come from injected conditions (powerflow.conditions: manual
toggles and event scenarios), not from the physics.
"""

from enum import IntEnum, IntFlag

from powerflow.models.bess import BessOutput, BessStatus
from powerflow.models.pv import PvOutput, PvStatus

VOLTAGE_LOW_PU = 0.95
VOLTAGE_HIGH_PU = 1.05
SOC_WARNING_MARGIN_PCT = 5.0  # warn this close to the SOC limits
TRANSFORMER_OVERLOAD_PCT = 100.0
LOW_POWER_FACTOR = 0.9
# Below this share of the POI's apparent power, P and Q are "zero" for the flags.
POI_IDLE_KW = 1.0


class BessOperatingState(IntEnum):
    OFF = 0
    STANDBY = 1
    CHARGING = 2
    DISCHARGING = 3
    FAULT = 4


class BessAlarm(IntFlag):
    NONE = 0
    SOC_LOW_WARNING = 1 << 0
    SOC_HIGH_WARNING = 1 << 1
    UNDERVOLTAGE = 1 << 2
    OVERVOLTAGE = 1 << 3
    TRANSFORMER_OVERLOAD = 1 << 4
    OVER_TEMPERATURE = 1 << 5  # an injected over_temperature fault
    COMM_LOSS = 1 << 6  # injected comm loss: the published values are frozen


class PvInverterState(IntEnum):
    OFF = 0
    SLEEPING = 1
    MPPT = 2
    THROTTLED = 3
    FAULT = 4


class PvAlarm(IntFlag):
    NONE = 0
    UNDERVOLTAGE = 1 << 0
    OVERVOLTAGE = 1 << 1
    TRANSFORMER_OVERLOAD = 1 << 2
    GROUND_FAULT = 1 << 3  # an injected ground_fault fault
    DC_OVERVOLTAGE = 1 << 4  # an injected dc_overvoltage fault
    COMM_LOSS = 1 << 5  # injected comm loss: the published values are frozen


class LoadSupplyState(IntEnum):
    DE_ENERGIZED = 0
    ENERGIZED = 1


class LoadAlarm(IntFlag):
    NONE = 0
    UNDERVOLTAGE = 1 << 0
    OVERVOLTAGE = 1 << 1
    # bit 2 is pae.LoadAlrm OVERLOAD (not simulated)
    COMM_LOSS = 1 << 3  # injected comm loss: the published values are frozen


class MeterState(IntEnum):
    OK = 0
    STALE = 1  # the power flow didn't converge, or comm loss: values are the last good ones


class BreakerState(IntEnum):
    OPEN = 0
    CLOSED = 1


class MeterAlarm(IntFlag):
    NONE = 0
    UNDERVOLTAGE = 1 << 0
    OVERVOLTAGE = 1 << 1
    EXPORTING = 1 << 2
    IMPORTING = 1 << 3
    LOW_POWER_FACTOR = 1 << 4


class SiteAlarm(IntFlag):
    NONE = 0
    NOT_CONVERGED = 1 << 0  # the latest power flow failed
    OVERRUN = 1 << 1  # at least one real-time tick was skipped since reset
    TEST_MODE = 1 << 2


def _voltage_bits(v_pu: float, low: IntFlag, high: IntFlag) -> int:
    if v_pu <= 0:  # no network result yet
        return 0
    if v_pu < VOLTAGE_LOW_PU:
        return int(low)
    if v_pu > VOLTAGE_HIGH_PU:
        return int(high)
    return 0


def bess_operating_state(output: BessOutput) -> BessOperatingState:
    if output.status is BessStatus.FAULT:
        return BessOperatingState.FAULT
    if output.status is BessStatus.OFFLINE:
        return BessOperatingState.OFF
    if output.p_kw > 0:
        return BessOperatingState.DISCHARGING
    if output.p_kw < 0:
        return BessOperatingState.CHARGING
    return BessOperatingState.STANDBY


def bess_alarms(
    soc_pct: float,
    soc_min_pct: float,
    soc_max_pct: float,
    v_lv_pu: float,
    transformer_loading_pct: float,
) -> BessAlarm:
    flags = _voltage_bits(v_lv_pu, BessAlarm.UNDERVOLTAGE, BessAlarm.OVERVOLTAGE)
    if soc_pct <= soc_min_pct + SOC_WARNING_MARGIN_PCT:
        flags |= BessAlarm.SOC_LOW_WARNING
    if soc_pct >= soc_max_pct - SOC_WARNING_MARGIN_PCT:
        flags |= BessAlarm.SOC_HIGH_WARNING
    if transformer_loading_pct > TRANSFORMER_OVERLOAD_PCT:
        flags |= BessAlarm.TRANSFORMER_OVERLOAD
    return BessAlarm(flags)


def pv_inverter_state(output: PvOutput) -> PvInverterState:
    match output.status:
        case PvStatus.FAULT:
            return PvInverterState.FAULT
        case PvStatus.OFFLINE:
            return PvInverterState.OFF
        case PvStatus.OFF:
            return PvInverterState.SLEEPING  # no sun: waiting for irradiance
        case PvStatus.CURTAILED:
            return PvInverterState.THROTTLED
        case PvStatus.PRODUCING:
            return PvInverterState.MPPT


def pv_alarms(v_lv_pu: float, transformer_loading_pct: float) -> PvAlarm:
    flags = _voltage_bits(v_lv_pu, PvAlarm.UNDERVOLTAGE, PvAlarm.OVERVOLTAGE)
    if transformer_loading_pct > TRANSFORMER_OVERLOAD_PCT:
        flags |= PvAlarm.TRANSFORMER_OVERLOAD
    return PvAlarm(flags)


def load_supply_state(v_pu: float) -> LoadSupplyState:
    return LoadSupplyState.ENERGIZED if v_pu > 0 else LoadSupplyState.DE_ENERGIZED


def load_alarms(v_pu: float) -> LoadAlarm:
    return LoadAlarm(_voltage_bits(v_pu, LoadAlarm.UNDERVOLTAGE, LoadAlarm.OVERVOLTAGE))


def meter_state(converged: bool, comm_lost: bool = False) -> MeterState:
    return MeterState.OK if converged and not comm_lost else MeterState.STALE


def breaker_state(closed: bool) -> BreakerState:
    return BreakerState.CLOSED if closed else BreakerState.OPEN


def meter_alarms(p_kw: float, v_pu: float, pf: float, s_kva: float) -> MeterAlarm:
    flags = _voltage_bits(v_pu, MeterAlarm.UNDERVOLTAGE, MeterAlarm.OVERVOLTAGE)
    if p_kw > POI_IDLE_KW:
        flags |= MeterAlarm.EXPORTING
    elif p_kw < -POI_IDLE_KW:
        flags |= MeterAlarm.IMPORTING
    if s_kva > POI_IDLE_KW and abs(pf) < LOW_POWER_FACTOR:
        flags |= MeterAlarm.LOW_POWER_FACTOR
    return MeterAlarm(flags)


def site_alarms(converged: bool | None, overrun_count: int, test_mode: bool) -> SiteAlarm:
    flags = SiteAlarm.NONE
    if converged is False:
        flags |= SiteAlarm.NOT_CONVERGED
    if overrun_count > 0:
        flags |= SiteAlarm.OVERRUN
    if test_mode:
        flags |= SiteAlarm.TEST_MODE
    return flags
