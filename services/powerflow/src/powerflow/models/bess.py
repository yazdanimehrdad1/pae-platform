"""Battery energy storage model: inverter limits + state of charge. Pure Python (no solver).

Generator convention: P > 0 discharges (injects), P < 0 charges.

Each step the setpoint goes through, in order:
1. mode: `offline` forces P = Q = 0 at once; `idle` targets P = Q = 0 (through the ramp).
2. P rating (P_LIMIT), then the S circle with the configured priority (S_LIMIT).
3. ramp: |P − P_previous| ≤ ramp·dt (RAMP_LIMIT).
4. SOC: P limited so the step's energy lands SOC exactly on its limit (SOC_LIMIT). The BMS
   limit wins over the ramp.
5. Q is trimmed to fit the S circle with the final P (S_LIMIT).
"""

from dataclasses import dataclass, replace
from enum import IntEnum, IntFlag, StrEnum

from powerflow.models.common import (
    RATING_TOLERANCE,
    apparent_power,
    clamp,
    limit_to_s_circle,
    trim_q_to_s_circle,
)
from powerflow.site_config.models import BessConfig, Priority

SECONDS_PER_HOUR = 3600.0


class BessMode(StrEnum):
    IDLE = "idle"
    PQ = "pq"
    OFFLINE = "offline"


# Integer codes for the enum16 point `mode_cmd`.
BESS_MODE_CODES: dict[BessMode, int] = {BessMode.IDLE: 0, BessMode.PQ: 1, BessMode.OFFLINE: 2}


class BessStatus(IntEnum):
    IDLE = 0
    RUNNING = 1
    OFFLINE = 2
    FAULT = 3  # tripped (an injected asset_fault condition)


class BessFlag(IntFlag):
    NONE = 0
    P_LIMIT = 1
    S_LIMIT = 2
    SOC_LIMIT = 4
    RAMP_LIMIT = 8


@dataclass(frozen=True)
class BessParams:
    p_discharge_max_kw: float
    p_charge_max_kw: float
    s_rated_kva: float
    capacity_kwh: float
    soc_min_pct: float
    soc_max_pct: float
    eta_charge: float
    eta_discharge: float
    ramp_kw_per_s: float | None
    priority: Priority
    aux_load_kw: float

    @classmethod
    def from_config(cls, config: BessConfig) -> "BessParams":
        return cls(
            p_discharge_max_kw=config.inverter.p_discharge_max_kw,
            p_charge_max_kw=config.inverter.p_charge_max_kw,
            s_rated_kva=config.inverter.s_rated_kva,
            capacity_kwh=config.battery.capacity_kwh,
            soc_min_pct=config.battery.soc_min_pct,
            soc_max_pct=config.battery.soc_max_pct,
            eta_charge=config.battery.efficiency.eta_charge,
            eta_discharge=config.battery.efficiency.eta_discharge,
            ramp_kw_per_s=config.inverter.ramp_kw_per_s,
            priority=config.inverter.priority,
            aux_load_kw=config.battery.aux_load_kw,
        )


@dataclass(frozen=True)
class BessSetpoint:
    p_kw: float = 0.0
    q_kvar: float = 0.0
    mode: BessMode = BessMode.IDLE


@dataclass(frozen=True)
class BessState:
    soc_pct: float
    p_kw: float = 0.0  # actual P delivered in the previous step (the ramp starts from it)
    q_kvar: float = 0.0


@dataclass(frozen=True)
class BessOutput:
    p_cmd_kw: float  # what the inverter is commanded after mode + static limits
    q_cmd_kvar: float
    p_kw: float  # actual, after every limit
    q_kvar: float
    flags: BessFlag
    status: BessStatus
    aux_p_kw: float

    @property
    def s_kva(self) -> float:
        return apparent_power(self.p_kw, self.q_kvar)


def clamp_static(params: BessParams, p_kw: float, q_kvar: float) -> tuple[float, float, BessFlag]:
    """Limits that don't depend on state: the P ratings, then the S circle. Used both when a
    setpoint is written (to report clamping) and on every step."""
    flags = BessFlag.NONE
    p_limited = clamp(p_kw, -params.p_charge_max_kw, params.p_discharge_max_kw)
    if p_limited != p_kw:
        flags |= BessFlag.P_LIMIT
    p_limited, q_limited, s_limited = limit_to_s_circle(
        p_limited, q_kvar, params.s_rated_kva, params.priority
    )
    if s_limited:
        flags |= BessFlag.S_LIMIT
    return p_limited, q_limited, flags


def stored_energy_kwh(params: BessParams, soc_pct: float) -> float:
    return params.capacity_kwh * soc_pct / 100.0


def energy_available_kwh(params: BessParams, soc_pct: float) -> tuple[float, float]:
    """(dischargeable AC energy, chargeable AC energy) in kWh, after efficiencies."""
    stored = stored_energy_kwh(params, soc_pct)
    above_min = max(stored - stored_energy_kwh(params, params.soc_min_pct), 0.0)
    below_max = max(stored_energy_kwh(params, params.soc_max_pct) - stored, 0.0)
    return above_min * params.eta_discharge, below_max / params.eta_charge


def p_available_kw(params: BessParams, soc_pct: float, dt_s: float) -> tuple[float, float]:
    """(max discharge P, max charge P) in kW for a step of dt_s, from ratings and SOC.
    Both are magnitudes (≥ 0)."""
    discharge_kwh, charge_kwh = energy_available_kwh(params, soc_pct)
    hours = dt_s / SECONDS_PER_HOUR
    return (
        min(params.p_discharge_max_kw, discharge_kwh / hours),
        min(params.p_charge_max_kw, charge_kwh / hours),
    )


def dispatch(
    params: BessParams, state: BessState, setpoint: BessSetpoint, dt_s: float
) -> BessOutput:
    """Apply one step's setpoint to the inverter and battery limits (see the module docstring)."""
    if setpoint.mode is BessMode.OFFLINE:
        return BessOutput(0.0, 0.0, 0.0, 0.0, BessFlag.NONE, BessStatus.OFFLINE, params.aux_load_kw)

    if setpoint.mode is BessMode.IDLE:
        p_cmd, q_cmd, flags = 0.0, 0.0, BessFlag.NONE
        status = BessStatus.IDLE
    else:
        p_cmd, q_cmd, flags = clamp_static(params, setpoint.p_kw, setpoint.q_kvar)
        status = BessStatus.RUNNING

    p_kw = p_cmd
    if params.ramp_kw_per_s is not None:
        max_step = params.ramp_kw_per_s * dt_s
        p_ramped = clamp(p_kw, state.p_kw - max_step, state.p_kw + max_step)
        if abs(p_ramped - p_kw) > RATING_TOLERANCE * max(abs(p_kw), 1.0):
            flags |= BessFlag.RAMP_LIMIT
        p_kw = p_ramped

    p_discharge_max, p_charge_max = p_available_kw(params, state.soc_pct, dt_s)
    p_soc = clamp(p_kw, -p_charge_max, p_discharge_max)
    if p_soc != p_kw:
        # Flag it only when the SOC (not the rating) is what bound.
        if p_kw > 0 and p_discharge_max < params.p_discharge_max_kw:
            flags |= BessFlag.SOC_LIMIT
        if p_kw < 0 and p_charge_max < params.p_charge_max_kw:
            flags |= BessFlag.SOC_LIMIT
        p_kw = p_soc

    q_kvar, s_limited = trim_q_to_s_circle(p_kw, q_cmd, params.s_rated_kva)
    if s_limited:
        flags |= BessFlag.S_LIMIT

    return BessOutput(p_cmd, q_cmd, p_kw, q_kvar, flags, status, params.aux_load_kw)


def integrate(params: BessParams, state: BessState, output: BessOutput, dt_s: float) -> BessState:
    """Advance SOC by the actual P over dt_s: discharge draws P/η_d from the cells, charge stores
    |P|·η_c. SOC is clamped to its limits to absorb float round-off."""
    hours = dt_s / SECONDS_PER_HOUR
    if output.p_kw >= 0:
        delta_kwh = -output.p_kw / params.eta_discharge * hours
    else:
        delta_kwh = -output.p_kw * params.eta_charge * hours
    soc_pct = state.soc_pct + delta_kwh / params.capacity_kwh * 100.0
    soc_pct = clamp(soc_pct, params.soc_min_pct, params.soc_max_pct)
    return replace(state, soc_pct=soc_pct, p_kw=output.p_kw, q_kvar=output.q_kvar)
