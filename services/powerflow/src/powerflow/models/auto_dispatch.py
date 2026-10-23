"""Auto dispatch: cycle a BESS inside an SOC window without an EMS. Pure Python.

A BESS discharges at `discharge_pct` % of its discharge rating until SOC reaches the window's
low edge, then charges at `charge_pct` % of its charge rating up to the high edge, and so on.
The direction only flips at an edge (hysteresis). Per BESS, it can:
- rest at an edge (P = 0) for `rest_s` of sim time before turning;
- add Gaussian noise to the target power (std in % of it, never past the rating);
- ramp its command at most `ramp_kw_per_s` (the inverter's own ramp still applies after);
- start in a chosen direction, and hold a fixed Q.

P is capped each step so the step's energy lands SOC exactly on the window edge (the same
calculation as the battery's own SOC limit, on the window instead of soc_min..soc_max).
"""

from dataclasses import dataclass, replace
from enum import StrEnum

from powerflow.models.bess import BessMode, BessParams, BessSetpoint, p_available_kw
from powerflow.models.common import clamp

# How close to an edge (in SOC %) counts as reaching it.
SOC_LIMIT_TOLERANCE_PCT = 1e-6


class AutoDispatchDirection(StrEnum):
    CHARGE = "charge"
    DISCHARGE = "discharge"


class AutoDispatchPhase(StrEnum):
    CHARGING = "charging"
    DISCHARGING = "discharging"
    RESTING = "resting"  # at an edge, P = 0 until the rest is over


@dataclass(frozen=True)
class AutoDispatchSettings:
    """One BESS's resolved settings (site defaults with its overrides applied)."""

    soc_low_pct: float
    soc_high_pct: float
    discharge_pct: float
    charge_pct: float
    rest_s: float = 0.0
    p_noise_std_pct: float = 0.0
    ramp_kw_per_s: float | None = None
    start_direction: AutoDispatchDirection | None = None
    q_kvar: float = 0.0


@dataclass(frozen=True)
class AutoDispatchBessState:
    direction: AutoDispatchDirection  # where it goes (after the rest, if resting)
    resting_until_s: float | None = None  # sim time (epoch s) the rest ends; None = not resting
    p_cmd_kw: float = 0.0  # the last commanded P (the ramp starts from it)

    @property
    def phase(self) -> AutoDispatchPhase:
        if self.resting_until_s is not None:
            return AutoDispatchPhase.RESTING
        if self.direction is AutoDispatchDirection.CHARGE:
            return AutoDispatchPhase.CHARGING
        return AutoDispatchPhase.DISCHARGING


def initial_state(settings: AutoDispatchSettings, soc_pct: float) -> AutoDispatchBessState:
    """The chosen start direction, or: discharge from above the middle of the window."""
    if settings.start_direction is not None:
        return AutoDispatchBessState(settings.start_direction)
    middle = (settings.soc_low_pct + settings.soc_high_pct) / 2.0
    if soc_pct > middle:
        return AutoDispatchBessState(AutoDispatchDirection.DISCHARGE)
    return AutoDispatchBessState(AutoDispatchDirection.CHARGE)


def advance(
    params: BessParams,
    settings: AutoDispatchSettings,
    state: AutoDispatchBessState,
    soc_pct: float,
    t_s: float,
    dt_s: float,
    noise_draw: float,
) -> tuple[AutoDispatchBessState, BessSetpoint]:
    """One step: turn (and maybe rest) at an edge, then the commanded P for a step of dt_s
    ending at sim time t_s. `noise_draw` is a standard-normal draw (the caller seeds it)."""
    direction, resting_until_s = state.direction, state.resting_until_s
    turn_to: AutoDispatchDirection | None = None
    if soc_pct <= settings.soc_low_pct + SOC_LIMIT_TOLERANCE_PCT:
        turn_to = AutoDispatchDirection.CHARGE
    elif soc_pct >= settings.soc_high_pct - SOC_LIMIT_TOLERANCE_PCT:
        turn_to = AutoDispatchDirection.DISCHARGE
    if turn_to is not None and turn_to is not direction:
        direction = turn_to
        resting_until_s = t_s + settings.rest_s if settings.rest_s > 0 else None
    if resting_until_s is not None and t_s >= resting_until_s:
        resting_until_s = None

    if resting_until_s is not None:
        target_kw = 0.0
    else:
        if direction is AutoDispatchDirection.DISCHARGE:
            rating, power_pct = params.p_discharge_max_kw, settings.discharge_pct
        else:
            rating, power_pct = params.p_charge_max_kw, settings.charge_pct
        magnitude = (
            rating * power_pct / 100.0 * (1.0 + noise_draw * settings.p_noise_std_pct / 100.0)
        )
        magnitude = clamp(magnitude, 0.0, rating)
        target_kw = magnitude if direction is AutoDispatchDirection.DISCHARGE else -magnitude

    p_kw = target_kw
    if settings.ramp_kw_per_s is not None:
        max_change = settings.ramp_kw_per_s * dt_s
        p_kw = clamp(p_kw, state.p_cmd_kw - max_change, state.p_cmd_kw + max_change)
    window = replace(params, soc_min_pct=settings.soc_low_pct, soc_max_pct=settings.soc_high_pct)
    p_discharge_max, p_charge_max = p_available_kw(window, soc_pct, dt_s)
    p_kw = clamp(p_kw, -p_charge_max, p_discharge_max)

    new_state = AutoDispatchBessState(direction, resting_until_s, p_kw)
    return new_state, BessSetpoint(p_kw=p_kw, q_kvar=settings.q_kvar, mode=BessMode.PQ)
