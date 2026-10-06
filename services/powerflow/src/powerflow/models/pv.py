"""PV plant model: available power, curtailment, Q / power factor control. Pure Python.

Available P comes from the profile, either as AC kW directly or from irradiance
(P = dc_kwp · G/1000), then losses, then clipping at the inverter's p_max_kw.
Actual P = min(available, curtailment limit), then the S circle:
- Q mode: the configured priority decides whether P or Q gives way.
- PF mode: P and Q scale down together, so the power factor holds.
"""

import math
from dataclasses import dataclass
from enum import IntEnum, IntFlag

from powerflow.models.common import (
    RATING_TOLERANCE,
    apparent_power,
    clamp,
    limit_to_s_circle,
    power_factor,
    q_from_power_factor,
)
from powerflow.site_config.models import Priority, PvAvailabilitySource, PvConfig

STANDARD_IRRADIANCE_WM2 = 1000.0


class PvQMode(IntEnum):
    Q = 0
    PF = 1


class PvStatus(IntEnum):
    OFF = 0  # nothing available (night)
    PRODUCING = 1
    CURTAILED = 2
    OFFLINE = 3  # disconnected: its breaker is open, or the site is de-energised
    FAULT = 4  # tripped (an injected fault)


class PvFlag(IntFlag):
    NONE = 0
    CURTAILED = 1
    S_LIMIT = 2
    CLIPPED = 4


@dataclass(frozen=True)
class PvParams:
    dc_kwp: float
    p_max_kw: float
    s_rated_kva: float
    loss_factor: float
    priority: Priority
    source: PvAvailabilitySource

    @classmethod
    def from_config(cls, config: PvConfig) -> "PvParams":
        return cls(
            dc_kwp=config.dc_kwp,
            p_max_kw=config.inverter.p_max_kw,
            s_rated_kva=config.inverter.s_rated_kva,
            loss_factor=config.loss_factor,
            priority=config.inverter.priority,
            source=config.availability.source,
        )


@dataclass(frozen=True)
class PvSetpoint:
    """A normalized PV setpoint. p_limit_kw = p_max_kw means no curtailment."""

    p_limit_kw: float
    q_mode: PvQMode = PvQMode.Q
    q_kvar: float = 0.0
    pf: float = 1.0

    @classmethod
    def unconstrained(cls, params: PvParams) -> "PvSetpoint":
        return cls(p_limit_kw=params.p_max_kw)


@dataclass(frozen=True)
class PvAvailability:
    p_available_kw: float  # after losses and clipping
    clipped: bool
    irradiance_wm2: float  # 0 in ac_kw mode


@dataclass(frozen=True)
class PvOutput:
    p_available_kw: float
    p_limit_kw: float
    p_kw: float
    q_kvar: float
    flags: PvFlag
    status: PvStatus
    irradiance_wm2: float

    @property
    def s_kva(self) -> float:
        return apparent_power(self.p_kw, self.q_kvar)

    @property
    def pf(self) -> float:
        return power_factor(self.p_kw, self.q_kvar)

    @property
    def curtailment_kw(self) -> float:
        return max(self.p_available_kw - self.p_kw, 0.0)


def availability(params: PvParams, profile_value: float) -> PvAvailability:
    """Available AC power for one profile value (kW in ac_kw mode, W/m² in irradiance mode)."""
    profile_value = max(profile_value, 0.0)
    if params.source is PvAvailabilitySource.IRRADIANCE:
        p_kw = params.dc_kwp * profile_value / STANDARD_IRRADIANCE_WM2
        irradiance = profile_value
    else:
        p_kw = profile_value
        irradiance = 0.0
    p_kw *= 1.0 - params.loss_factor
    clipped = p_kw > params.p_max_kw * (1 + RATING_TOLERANCE)
    return PvAvailability(min(p_kw, params.p_max_kw), clipped, irradiance)


def dispatch(params: PvParams, setpoint: PvSetpoint, available: PvAvailability) -> PvOutput:
    flags = PvFlag.CLIPPED if available.clipped else PvFlag.NONE
    p_limit = clamp(setpoint.p_limit_kw, 0.0, params.p_max_kw)
    p_kw = min(available.p_available_kw, p_limit)
    if p_kw < available.p_available_kw:
        flags |= PvFlag.CURTAILED

    if setpoint.q_mode is PvQMode.PF:
        q_kvar = q_from_power_factor(p_kw, setpoint.pf)
        s_kva = math.hypot(p_kw, q_kvar)
        if s_kva > params.s_rated_kva * (1 + RATING_TOLERANCE):
            ratio = params.s_rated_kva / s_kva
            p_kw, q_kvar = p_kw * ratio, q_kvar * ratio
            flags |= PvFlag.S_LIMIT
    else:
        # PV can't absorb P: with Q priority, P gives way down to 0, never below.
        p_kw, q_kvar, s_limited = limit_to_s_circle(
            p_kw, setpoint.q_kvar, params.s_rated_kva, params.priority
        )
        p_kw = max(p_kw, 0.0)
        if s_limited:
            flags |= PvFlag.S_LIMIT

    if available.p_available_kw <= 0:
        status = PvStatus.OFF
    elif flags & PvFlag.CURTAILED:
        status = PvStatus.CURTAILED
    else:
        status = PvStatus.PRODUCING
    return PvOutput(
        p_available_kw=available.p_available_kw,
        p_limit_kw=p_limit,
        p_kw=p_kw,
        q_kvar=q_kvar,
        flags=flags,
        status=status,
        irradiance_wm2=available.irradiance_wm2,
    )
