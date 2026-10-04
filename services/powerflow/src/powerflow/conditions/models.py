"""Condition changes (what a toggle or a scenario event does), the conditions they build up, and
the pure functions that validate and apply them.

- **breaker:** open/close an asset's breaker (its id) or the POI breaker ("poi").
- **asset_fault:** trip a BESS or PV inverter (P = Q = 0, FAULT status), with a cause that sets
  the matching alarm bit; `active: false` clears it.
- **comm_loss:** freeze what an asset, feeder meter or the POI meter publishes (the physics keep
  running); the COMM_LOSS alarm bit (meters: STALE) is set until it clears.
- **grid_voltage / grid_frequency:** the source voltage (sag/swell) and the reported frequency;
  null restores the site config's value (nominal frequency).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from powerflow.errors import ConditionError, UnknownAssetError
from powerflow.site_config import POI_BUS_ID, SiteConfig


class FaultCause(StrEnum):
    TRIP = "trip"  # any asset
    OVER_TEMPERATURE = "over_temperature"  # BESS
    GROUND_FAULT = "ground_fault"  # PV
    DC_OVERVOLTAGE = "dc_overvoltage"  # PV


BESS_CAUSES = frozenset({FaultCause.TRIP, FaultCause.OVER_TEMPERATURE})
PV_CAUSES = frozenset({FaultCause.TRIP, FaultCause.GROUND_FAULT, FaultCause.DC_OVERVOLTAGE})


class CommTarget(StrEnum):
    ASSET = "asset"  # a BESS, PV or load (its id)
    METER = "meter"  # a feeder meter (its id)
    POI_METER = "poi_meter"  # the POI meter (no id)


class _Change(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BreakerChange(_Change):
    type: Literal["breaker"] = "breaker"
    breaker: str = Field(description='An asset id (BESS, PV or load), or "poi".')
    closed: bool


class AssetFaultChange(_Change):
    type: Literal["asset_fault"] = "asset_fault"
    asset_id: str = Field(description="A BESS or PV id.")
    active: bool = Field(default=True, description="false clears the fault.")
    cause: FaultCause = Field(
        default=FaultCause.TRIP,
        description="trip (any); over_temperature (BESS); ground_fault, dc_overvoltage (PV).",
    )


class CommLossChange(_Change):
    type: Literal["comm_loss"] = "comm_loss"
    target: CommTarget
    id: str | None = Field(
        default=None, description="The asset or feeder meter id (none for poi_meter)."
    )
    active: bool = Field(default=True, description="false restores communication.")


class GridVoltageChange(_Change):
    type: Literal["grid_voltage"] = "grid_voltage"
    vm_pu: float | None = Field(
        ge=0.5, le=1.5, description="Source voltage (pu); null restores grid.vm_pu."
    )


class GridFrequencyChange(_Change):
    type: Literal["grid_frequency"] = "grid_frequency"
    hz: float | None = Field(ge=55, le=65, description="Grid frequency; null restores nominal.")


ConditionChange = Annotated[
    BreakerChange | AssetFaultChange | CommLossChange | GridVoltageChange | GridFrequencyChange,
    Field(discriminator="type"),
]

# (target, id); the POI meter's id is "".
CommKey = tuple[CommTarget, str]


Key = TypeVar("Key")
Value = TypeVar("Value")


def _frozen(mapping: Mapping[Key, Value]) -> Mapping[Key, Value]:
    return MappingProxyType(dict(mapping))


@dataclass(frozen=True)
class Conditions:
    open_breakers: frozenset[str] = frozenset()
    faults: Mapping[str, FaultCause] = field(default_factory=lambda: _frozen({}))
    comm_loss: Mapping[CommKey, int] = field(default_factory=lambda: _frozen({}))  # → since step
    grid_vm_pu: float | None = None
    grid_hz: float | None = None

    def comm_lost(self, target: CommTarget, asset_id: str = "") -> bool:
        return (target, asset_id) in self.comm_loss


def initial_conditions(config: SiteConfig) -> Conditions:
    """The site config's breaker positions; nothing else injected."""
    assets = [*config.bess, *config.pv, *config.loads]
    open_breakers = {asset.id for asset in assets if not asset.breaker.closed}
    if not config.poi.breaker.closed:
        open_breakers.add(POI_BUS_ID)
    return Conditions(open_breakers=frozenset(open_breakers))


def validate_change(change: ConditionChange, config: SiteConfig) -> None:
    """Raises UnknownAssetError (no such asset/meter) or ConditionError (doesn't apply)."""
    bess_ids = {bess.id for bess in config.bess}
    pv_ids = {pv.id for pv in config.pv}
    asset_ids = bess_ids | pv_ids | {load.id for load in config.loads}
    match change:
        case BreakerChange(breaker=breaker):
            if breaker != POI_BUS_ID and breaker not in asset_ids:
                raise UnknownAssetError(f"no breaker {breaker!r} (an asset id or 'poi')")
        case AssetFaultChange(asset_id=asset_id, cause=cause):
            if asset_id in bess_ids:
                allowed = BESS_CAUSES
            elif asset_id in pv_ids:
                allowed = PV_CAUSES
            elif asset_id in asset_ids:
                raise ConditionError(f"{asset_id!r} is a load: only BESS and PV can fault")
            else:
                raise UnknownAssetError(f"no BESS or PV {asset_id!r}")
            if cause not in allowed:
                raise ConditionError(
                    f"{cause} doesn't apply to {asset_id!r} (allowed: {sorted(allowed)})"
                )
        case CommLossChange(target=CommTarget.POI_METER, id=target_id):
            if target_id not in (None, ""):
                raise ConditionError("comm_loss on poi_meter takes no id")
        case CommLossChange(target=CommTarget.ASSET, id=target_id):
            if target_id not in asset_ids:
                raise UnknownAssetError(f"no asset {target_id!r}")
        case CommLossChange(target=CommTarget.METER, id=target_id):
            if target_id not in {meter.id for meter in config.meters}:
                raise UnknownAssetError(f"no feeder meter {target_id!r}")
        case _:
            pass  # grid changes: the field bounds are the whole check


def apply_change(conditions: Conditions, change: ConditionChange, step_index: int) -> Conditions:
    """The conditions after `change` (already validated). `step_index` is the current step: a
    comm loss records it (it freezes what was published at that step)."""
    match change:
        case BreakerChange(breaker=breaker, closed=closed):
            opened = set(conditions.open_breakers)
            if closed:
                opened.discard(breaker)
            else:
                opened.add(breaker)
            return replace(conditions, open_breakers=frozenset(opened))
        case AssetFaultChange(asset_id=asset_id, active=active, cause=cause):
            faults = dict(conditions.faults)
            if active:
                faults[asset_id] = cause
            else:
                faults.pop(asset_id, None)
            return replace(conditions, faults=_frozen(faults))
        case CommLossChange(target=target, id=target_id, active=active):
            key: CommKey = (target, target_id or "")
            comm_loss = dict(conditions.comm_loss)
            if active:
                comm_loss.setdefault(key, step_index)
            else:
                comm_loss.pop(key, None)
            return replace(conditions, comm_loss=_frozen(comm_loss))
        case GridVoltageChange(vm_pu=vm_pu):
            return replace(conditions, grid_vm_pu=vm_pu)
        case GridFrequencyChange(hz=hz):
            return replace(conditions, grid_hz=hz)


# -- reporting ---------------------------------------------------------------------------------


BreakerKind = Literal["poi", "bess", "pv", "load"]


class BreakerStatus(BaseModel):
    id: str = Field(description='The asset id, or "poi".')
    kind: BreakerKind
    closed: bool


class FaultStatus(BaseModel):
    asset_id: str
    cause: FaultCause


class CommLossStatus(BaseModel):
    target: CommTarget
    id: str | None
    since_step: int = Field(description="The step whose values stay published.")


class ActiveConditions(BaseModel):
    """The true conditions (what's injected now), whatever comm loss hides."""

    breakers: list[BreakerStatus]
    faults: list[FaultStatus]
    comm_loss: list[CommLossStatus]
    grid_vm_pu: float | None = Field(description="Injected source voltage; null = grid.vm_pu.")
    grid_hz: float | None = Field(description="Injected frequency; null = nominal.")


def summary(conditions: Conditions, config: SiteConfig) -> ActiveConditions:
    def breaker(breaker_id: str, kind: BreakerKind) -> BreakerStatus:
        closed = breaker_id not in conditions.open_breakers
        return BreakerStatus(id=breaker_id, kind=kind, closed=closed)

    return ActiveConditions(
        breakers=[
            breaker(POI_BUS_ID, "poi"),
            *(breaker(bess.id, "bess") for bess in config.bess),
            *(breaker(pv.id, "pv") for pv in config.pv),
            *(breaker(load.id, "load") for load in config.loads),
        ],
        faults=[
            FaultStatus(asset_id=asset_id, cause=cause)
            for asset_id, cause in sorted(conditions.faults.items())
        ],
        comm_loss=[
            CommLossStatus(target=target, id=target_id or None, since_step=since)
            for (target, target_id), since in sorted(conditions.comm_loss.items())
        ],
        grid_vm_pu=conditions.grid_vm_pu,
        grid_hz=conditions.grid_hz,
    )
