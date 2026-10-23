"""Runtime battery overrides (PUT /assets/bess/{id}/battery): set a BESS's SOC now, and its
round-trip efficiency until the next activate or reset. They change the battery, not the
setpoint, so they work while auto dispatch drives it.

Every BESS starts at 100 % round trip (lossless) on activate and reset; `null` returns it to the
site config's efficiency."""

from dataclasses import replace

from pydantic import BaseModel, ConfigDict, Field

from powerflow.models.bess import BessParams

DEFAULT_ROUND_TRIP_PCT = 100.0


class BessBatteryRequest(BaseModel):
    """A partial update: a field left out keeps its value."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    soc_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Set the SOC now (one shot), clamped to the battery's soc_min..soc_max.",
    )
    round_trip_efficiency_pct: float | None = Field(
        default=None,
        ge=50,
        le=100,
        description="Round-trip efficiency, split evenly over charge and discharge. "
        "null: the site config's efficiency.",
    )


class BessBatteryState(BaseModel):
    asset_id: str
    soc_pct: float
    round_trip_efficiency_pct: float | None = Field(
        description="The override; null = the site config's efficiency."
    )
    eta_charge: float = Field(description="In effect.")
    eta_discharge: float = Field(description="In effect.")


def with_round_trip(config_params: BessParams, round_trip_pct: float | None) -> BessParams:
    """The params with the efficiency in effect: the config's (None), or the round trip split
    evenly (η_c = η_d = √RTE)."""
    if round_trip_pct is None:
        return config_params
    eta = (round_trip_pct / 100.0) ** 0.5
    return replace(config_params, eta_charge=eta, eta_discharge=eta)
