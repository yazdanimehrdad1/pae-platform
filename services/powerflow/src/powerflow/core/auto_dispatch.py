"""Auto dispatch settings and report: the request (site-wide defaults plus per-BESS overrides),
how they resolve per BESS against its battery, and what GET/PUT /sim/auto-dispatch return.

A field left out of an override falls back to the defaults, then to: the battery's
soc_min_pct..soc_max_pct window, no rest, no noise, no extra ramp, the automatic start
direction and Q = 0. The physics of one step are in `models/auto_dispatch.py`.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from powerflow.errors import AutoDispatchError
from powerflow.models.auto_dispatch import (
    AutoDispatchDirection,
    AutoDispatchPhase,
    AutoDispatchSettings,
)
from powerflow.models.bess import BessParams

DEFAULT_POWER_PCT = 50.0


class AutoDispatchBessSettings(BaseModel):
    """Settings for auto dispatch: as the site-wide defaults, or one BESS's overrides. Every field
    is optional; an omitted one falls back (override → defaults → built-in)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    included: bool | None = Field(
        default=None,
        description="false: auto dispatch leaves the BESS alone, and it takes setpoints as usual. "
        "Default true.",
    )
    soc_low_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Window low edge; default the battery's soc_min_pct.",
    )
    soc_high_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Window high edge; default the battery's soc_max_pct.",
    )
    rest_s: float | None = Field(
        default=None,
        ge=0,
        description="Idle at an edge for this long (sim s) before turning; default 0.",
    )
    p_noise_std_pct: float | None = Field(
        default=None,
        ge=0,
        le=50,
        description="Gaussian noise on the target P, std in % of it (seeded per step); default 0.",
    )
    ramp_kw_per_s: float | None = Field(
        default=None,
        gt=0,
        description="Max change of the command per sim second (the inverter's ramp still applies); "
        "default none.",
    )
    start_direction: AutoDispatchDirection | None = Field(
        default=None,
        description="Default: discharge from above the middle of the window, else charge.",
    )
    q_kvar: float | None = Field(default=None, description="Q held while cycling; default 0.")

    @model_validator(mode="after")
    def _window_order(self) -> Self:
        if (
            self.soc_low_pct is not None
            and self.soc_high_pct is not None
            and self.soc_low_pct >= self.soc_high_pct
        ):
            raise ValueError("soc_low_pct must be below soc_high_pct")
        return self


class AutoDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    enabled: bool
    power_pct: float = Field(
        default=DEFAULT_POWER_PCT,
        gt=0,
        le=100,
        description="% of each BESS's discharge/charge rating to drive it at.",
    )
    defaults: AutoDispatchBessSettings = Field(
        default_factory=AutoDispatchBessSettings, description="For every BESS."
    )
    bess: dict[str, AutoDispatchBessSettings] = Field(
        default_factory=dict, description="Per BESS id: what differs from the defaults."
    )


class AutoDispatchBess(BaseModel):
    asset_id: str
    included: bool
    phase: AutoDispatchPhase | None = Field(description="null while excluded.")
    direction: AutoDispatchDirection | None = Field(
        description="Where it goes (after the rest, if resting); null while excluded."
    )
    soc_pct: float
    soc_min_pct: float = Field(description="The battery's band.")
    soc_max_pct: float
    soc_low_pct: float | None = Field(description="The window it cycles in; null while excluded.")
    soc_high_pct: float | None
    rest_s: float | None
    rest_remaining_s: float | None = Field(description="Sim seconds left while resting.")
    p_noise_std_pct: float | None
    ramp_kw_per_s: float | None
    q_kvar: float | None


class AutoDispatchReport(BaseModel):
    enabled: bool
    power_pct: float | None = Field(description="% of each BESS's rating; null while off.")
    defaults: AutoDispatchBessSettings = Field(description="As sent; empty while off.")
    bess_overrides: dict[str, AutoDispatchBessSettings] = Field(
        description="As sent; empty while off."
    )
    bess: list[AutoDispatchBess] = Field(description="Every BESS while on; empty while off.")


def _first(fallback: float, *values: float | None) -> float:
    """The first value that is set, else `fallback`."""
    return next((value for value in values if value is not None), fallback)


def resolve(
    asset_id: str,
    params: BessParams,
    defaults: AutoDispatchBessSettings,
    override: AutoDispatchBessSettings | None,
) -> AutoDispatchSettings | None:
    """One BESS's settings, or None when it's excluded. AutoDispatchError when its window
    doesn't fit inside its battery's band (or ends up empty)."""
    override = override or AutoDispatchBessSettings()
    included = override.included if override.included is not None else defaults.included
    if included is False:
        return None
    low = _first(params.soc_min_pct, override.soc_low_pct, defaults.soc_low_pct)
    high = _first(params.soc_max_pct, override.soc_high_pct, defaults.soc_high_pct)
    if low < params.soc_min_pct or high > params.soc_max_pct:
        raise AutoDispatchError(
            f"BESS {asset_id!r}: the window {low:g}–{high:g} % must be inside its battery's "
            f"{params.soc_min_pct:g}–{params.soc_max_pct:g} %"
        )
    if low >= high:
        raise AutoDispatchError(f"BESS {asset_id!r}: soc_low_pct {low:g} must be below {high:g}")
    ramp = override.ramp_kw_per_s if override.ramp_kw_per_s is not None else defaults.ramp_kw_per_s
    start = (
        override.start_direction
        if override.start_direction is not None
        else defaults.start_direction
    )
    return AutoDispatchSettings(
        soc_low_pct=low,
        soc_high_pct=high,
        rest_s=_first(0.0, override.rest_s, defaults.rest_s),
        p_noise_std_pct=_first(0.0, override.p_noise_std_pct, defaults.p_noise_std_pct),
        ramp_kw_per_s=ramp,
        start_direction=start,
        q_kvar=_first(0.0, override.q_kvar, defaults.q_kvar),
    )
