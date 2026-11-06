"""
Powerflow 2BESS 1PV's helper functions: the pure decisions behind its alarms (no DB, no network,
no clock). The checks in powerflow_2bess_1pv_alarms.py read the points and call these.

Codes and bit labels are the point standard's (powerflow's docs/point-standard, served on Modbus):
701.InvSt, 701.Alrm, 701.ThrotSrc, 802.Evt1, 203.Evt, pae.GridMode and pae.PpcAlrm.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta

from helpers.reads.calculate_reads import translate_bitfield_to_named_map
from schemas.site_profiles.individual_sites.powerflow_2bess_1pv import LatestPointValue

# 701.InvSt
INV_STATE_RUNNING = 3
INV_STATE_FAULT = 6
# pae.GridMode: anything else (ISLANDED, TRANSITIONING, BLACKOUT) means the grid isn't there.
GRID_MODE_GRID_TIED = 0

# 701.Alrm. AC_DISCONNECT: the unit's own breaker is open, so it is out of service.
ALRM_AC_DISCONNECT = "AC_DISCONNECT"
ALRM_OVER_TEMP = "OVER_TEMP"
ALRM_BLOWN_STRING_FUSE = "BLOWN_STRING_FUSE"
# 701.ThrotSrc
THROT_DERATED = "DERATED"
# pae.PpcAlrm
PPC_DEVICE_COMM_LOSS = "DEVICE_COMM_LOSS"
PPC_POI_METER_FAIL = "POI_METER_FAIL"
# 203.Evt
METER_POWER_FAILURE = "M_EVENT_Power_Failure"

# 802.Evt1 bits that mean the battery stopped (or must stop): a fault.
BESS_EVT1_FAULT_BITS = frozenset(
    {
        "OVER_TEMP_ALARM",
        "UNDER_TEMP_ALARM",
        "OVER_CHARGE_CURRENT_ALARM",
        "OVER_DISCHARGE_CURRENT_ALARM",
        "OVER_VOLT_ALARM",
        "UNDER_VOLT_ALARM",
        "UNDER_SOC_MIN_ALARM",
        "OVER_SOC_MAX_ALARM",
        "TEMPERATURE_IMBALANCE_ALARM",
        "CONTACTOR_ERROR",
        "GROUND_FAULT",
        "OPEN_DOOR_ERROR",
        "OTHER_ALARM",
        "CONFIGURATION_ALARM",
    }
)
# 802.Evt1 bits that mean the battery runs on, derated or at risk: a warning. The SoC warnings
# are left out (powerflow sets them near every SoC limit; bess_soc_low/high cover SoC), and so is
# COMMUNICATION_ERROR (device_comm_loss covers comms).
BESS_EVT1_WARNING_BITS = frozenset(
    {
        "OVER_TEMP_WARNING",
        "UNDER_TEMP_WARNING",
        "OVER_CHARGE_CURRENT_WARNING",
        "OVER_DISCHARGE_CURRENT_WARNING",
        "OVER_VOLT_WARNING",
        "UNDER_VOLT_WARNING",
        "VOLTAGE_IMBALANCE_WARNING",
        "TEMPERATURE_IMBALANCE_WARNING",
        "CURRENT_IMBALANCE_WARNING",
        "FAN_ERROR",
        "OTHER_WARNING",
        "CONFIGURATION_WARNING",
    }
)


def set_bits(value: float, bitfield_detail: Mapping[str, str] | None) -> frozenset[str]:
    """The labels of the bits set in a bitfield value; empty for a point without bit labels."""
    if not bitfield_detail:
        return frozenset()
    named = translate_bitfield_to_named_map(value, dict(bitfield_detail))
    return frozenset(label for label, state in named.items() if state)


def has_code(point: LatestPointValue | None, code: int) -> bool:
    return point is not None and int(point.value) == code


def has_bit(point: LatestPointValue | None, label: str) -> bool:
    return point is not None and label in point.bits


def inverter_faulted(
    inv_state: LatestPointValue | None,
    alrm: LatestPointValue | None,
    evt1: LatestPointValue | None = None,
) -> bool:
    """The unit is in FAULT, its own breaker is open, or (BESS, given its Evt1) the battery
    reports a fault bit. Alrm's other bits are not used: the grid ones are the POI alarms' job,
    and a PV over-temperature warning sets the same OVER_TEMP bit as the fault."""
    return (
        has_code(inv_state, INV_STATE_FAULT)
        or has_bit(alrm, ALRM_AC_DISCONNECT)
        or (evt1 is not None and bool(evt1.bits & BESS_EVT1_FAULT_BITS))
    )


def bess_warnings(evt1: LatestPointValue | None) -> frozenset[str]:
    """The battery's set warning bits (BESS_EVT1_WARNING_BITS)."""
    return evt1.bits & BESS_EVT1_WARNING_BITS if evt1 is not None else frozenset()


def pv_derate_reasons(
    inv_state: LatestPointValue | None,
    alrm: LatestPointValue | None,
    throt_src: LatestPointValue | None,
) -> frozenset[str]:
    """Why the PV inverter runs derated: a blown string fuse, an over-temperature that hasn't
    tripped it (InvSt not FAULT), or a DERATED throttle source. Curtailment and clipping don't count."""
    reasons: set[str] = set()
    if has_bit(alrm, ALRM_BLOWN_STRING_FUSE):
        reasons.add(ALRM_BLOWN_STRING_FUSE)
    if has_bit(alrm, ALRM_OVER_TEMP) and not has_code(inv_state, INV_STATE_FAULT):
        reasons.add(ALRM_OVER_TEMP)
    if has_bit(throt_src, THROT_DERATED):
        reasons.add(THROT_DERATED)
    return frozenset(reasons)


def worst_voltage_deviation_pct(voltages_kv: list[float], nominal_kv: float) -> float | None:
    """The deviation from nominal (%, signed) of the voltage furthest from it; None without any."""
    if not voltages_kv:
        return None
    deviations = [(voltage / nominal_kv - 1.0) * 100.0 for voltage in voltages_kv]
    return max(deviations, key=abs)


def frequency_outside(hz: float, min_hz: float, max_hz: float) -> bool:
    return hz < min_hz or hz > max_hz


def loading_pct(apparent_power_kva: float, rating_kva: float) -> float:
    """Apparent power as a share of the rating, in percent (either flow direction)."""
    return abs(apparent_power_kva) / rating_kva * 100.0


def pv_performance_pct(
    active_power_kw: float, available_power_kw: float, rated_kw: float, daytime_min_pct: float
) -> float | None:
    """Produced power as a share of available power, in percent. None when there is too little
    sun to judge: available power below `daytime_min_pct` of the rating."""
    if available_power_kw < rated_kw * daytime_min_pct / 100.0:
        return None
    return active_power_kw / available_power_kw * 100.0


def pv_underperforming(
    inv_state: LatestPointValue | None,
    throt_src: LatestPointValue | None,
    performance_pct: float | None,
    min_pct: float,
) -> bool:
    """RUNNING, nothing throttling it (no ThrotSrc bit: not curtailed, clipped or derated), and
    producing less than `min_pct` of what is available."""
    return (
        has_code(inv_state, INV_STATE_RUNNING)
        and throt_src is not None
        and not throt_src.bits
        and performance_pct is not None
        and performance_pct < min_pct
    )


def stale_device_ids(
    last_success: Mapping[int, datetime], now: datetime, stale_after: timedelta
) -> list[int]:
    """The devices whose last successful poll is older than `stale_after`, by id. A device that
    has never reported isn't in `last_success`, so it isn't stale (nothing was lost)."""
    return sorted(device_id for device_id, at in last_success.items() if now - at > stale_after)
