"""SetpointService: the single path every interface uses to write a setpoint.

It validates the request (invalid → error), merges it into the asset's current setpoint,
applies the static limits (out of range → clamped, and reported), and stores the result for the
next step. Dynamic limits (SOC, ramp) are applied every step and reported in the measurements.
"""

import math
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from powerflow.core.engine import Engine
from powerflow.models import bess as bess_model
from powerflow.models import pv as pv_model

MIN_ABS_POWER_FACTOR = 0.8


class BessSetpointRequest(BaseModel):
    """A partial BESS setpoint: omitted fields keep their current value."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    p_kw: float | None = Field(default=None, description="+ discharge, − charge (kW).")
    q_kvar: float | None = Field(default=None, description="+ injecting vars (kvar).")
    mode: bess_model.BessMode | None = None


class PvSetpointRequest(BaseModel):
    """A partial PV setpoint: at most one of p_limit_kw / p_limit_pct and one of q_kvar / pf.
    Omitted fields keep their current value."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    p_limit_kw: float | None = Field(default=None, ge=0, description="Curtailment limit (kW).")
    p_limit_pct: float | None = Field(
        default=None, ge=0, le=100, description="Curtailment limit (% of p_max_kw)."
    )
    q_kvar: float | None = Field(default=None, description="Q setpoint; selects Q mode.")
    pf: float | None = Field(
        default=None,
        ge=-1,
        le=1,
        description="Power factor; + injecting vars, − absorbing; |pf| ≥ 0.8. Selects PF mode.",
    )

    @model_validator(mode="after")
    def _exclusive(self) -> Self:
        if self.p_limit_kw is not None and self.p_limit_pct is not None:
            raise ValueError("give p_limit_kw or p_limit_pct, not both")
        if self.q_kvar is not None and self.pf is not None:
            raise ValueError("give q_kvar or pf, not both")
        if self.pf is not None and abs(self.pf) < MIN_ABS_POWER_FACTOR:
            raise ValueError(f"|pf| must be ≥ {MIN_ABS_POWER_FACTOR}")
        return self


class BessSetpointState(BaseModel):
    p_kw: float
    q_kvar: float
    mode: bess_model.BessMode


class PvSetpointState(BaseModel):
    p_limit_kw: float
    p_limit_pct: float
    q_mode: str = Field(description='"q" or "pf".')
    q_kvar: float
    pf: float


class SetpointResult(BaseModel):
    asset_type: str
    asset_id: str
    requested: dict[str, float | str | None]
    accepted: BessSetpointState | PvSetpointState
    clamped: bool
    flags: list[str] = Field(description="Static limits that clamped the request.")


def bess_setpoint_state(setpoint: bess_model.BessSetpoint) -> BessSetpointState:
    return BessSetpointState(p_kw=setpoint.p_kw, q_kvar=setpoint.q_kvar, mode=setpoint.mode)


def pv_setpoint_state(setpoint: pv_model.PvSetpoint, params: pv_model.PvParams) -> PvSetpointState:
    return PvSetpointState(
        p_limit_kw=setpoint.p_limit_kw,
        p_limit_pct=setpoint.p_limit_kw / params.p_max_kw * 100.0,
        q_mode=setpoint.q_mode.name.lower(),
        q_kvar=setpoint.q_kvar,
        pf=setpoint.pf,
    )


class SetpointService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def bess(self, asset_id: str) -> BessSetpointState:
        return bess_setpoint_state(self._engine.setpoints.bess(asset_id))

    def pv(self, asset_id: str) -> PvSetpointState:
        params = self._engine.runtime.pv_asset(asset_id).params
        return pv_setpoint_state(self._engine.setpoints.pv(asset_id), params)

    def write_bess(self, asset_id: str, request: BessSetpointRequest) -> SetpointResult:
        params = self._engine.runtime.bess_asset(asset_id).params
        current = self._engine.setpoints.bess(asset_id)
        p_kw = request.p_kw if request.p_kw is not None else current.p_kw
        q_kvar = request.q_kvar if request.q_kvar is not None else current.q_kvar
        mode = request.mode if request.mode is not None else current.mode

        p_kw, q_kvar, flags = bess_model.clamp_static(params, p_kw, q_kvar)
        accepted = bess_model.BessSetpoint(p_kw=p_kw, q_kvar=q_kvar, mode=mode)
        self._engine.setpoints.set_bess(asset_id, accepted)
        flag_names = [
            member.name for member in bess_model.BessFlag if member in flags and member.name
        ]
        return SetpointResult(
            asset_type="bess",
            asset_id=asset_id,
            requested=request.model_dump(exclude_none=True, mode="json"),
            accepted=bess_setpoint_state(accepted),
            clamped=bool(flag_names),
            flags=flag_names,
        )

    def write_pv(self, asset_id: str, request: PvSetpointRequest) -> SetpointResult:
        params = self._engine.runtime.pv_asset(asset_id).params
        current = self._engine.setpoints.pv(asset_id)
        flags: list[str] = []

        p_limit_kw = current.p_limit_kw
        if request.p_limit_kw is not None:
            p_limit_kw = request.p_limit_kw
        elif request.p_limit_pct is not None:
            p_limit_kw = request.p_limit_pct / 100.0 * params.p_max_kw
        if p_limit_kw > params.p_max_kw:
            p_limit_kw = params.p_max_kw
            flags.append("P_LIMIT")

        q_mode, q_kvar, pf = current.q_mode, current.q_kvar, current.pf
        if request.q_kvar is not None:
            q_mode, q_kvar = pv_model.PvQMode.Q, request.q_kvar
            if abs(q_kvar) > params.s_rated_kva:
                q_kvar = math.copysign(params.s_rated_kva, q_kvar)
                flags.append("S_LIMIT")
        elif request.pf is not None:
            q_mode, pf = pv_model.PvQMode.PF, request.pf

        accepted = pv_model.PvSetpoint(p_limit_kw=p_limit_kw, q_mode=q_mode, q_kvar=q_kvar, pf=pf)
        self._engine.setpoints.set_pv(asset_id, accepted)
        return SetpointResult(
            asset_type="pv",
            asset_id=asset_id,
            requested=request.model_dump(exclude_none=True, mode="json"),
            accepted=pv_setpoint_state(accepted, params),
            clamped=bool(flags),
            flags=flags,
        )
