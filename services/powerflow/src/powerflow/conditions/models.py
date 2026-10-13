"""Condition changes (what a toggle or a scenario event does), the conditions they build up, and
the pure functions that validate and apply them.

- **breaker:** open/close an asset's breaker (its id) or the POI breaker ("poi").
- **asset_fault:** a cause from the fault catalog (fault_catalog.py) on a BESS or PV inverter. A
  fault trips it (P = Q = 0, FAULT status, the cause's alarm bits); a warning derates it. Several
  causes can be active on one asset. `active: false` clears the asset: its warnings go, its faults
  latch (FAULT and the bits stay) until an **alarm_reset**. A fault injected with `auto_restore`
  clears itself 2-10 min of sim time after injection (deterministic: seed, asset, cause, step).
- **comm_loss:** freeze what an asset, feeder meter or the POI meter publishes (the physics keep
  running); the COMM_LOSS alarm bit (meters: STALE) is set until it clears.
- **grid_voltage / grid_frequency:** the source voltage (sag/swell) and the reported frequency;
  null restores the site config's value (nominal frequency).
"""

import math
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal, TypeVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from powerflow.conditions.fault_catalog import (
    AUTO_RESTORE_MAX_S,
    AUTO_RESTORE_MIN_S,
    SEVERITY,
    AssetKind,
    FaultCause,
    Severity,
    catalog_order,
    cause_spec,
    causes_for,
)
from powerflow.errors import ConditionError, UnknownAssetError
from powerflow.site_config import POI_BUS_ID, SiteConfig

BESS_CAUSES = causes_for("bess")
PV_CAUSES = causes_for("pv")


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
    active: bool = Field(
        default=True,
        description="false clears the asset (every cause): warnings go, faults latch until an "
        "alarm_reset.",
    )
    cause: FaultCause = Field(
        default=FaultCause.TRIP,
        description="A cause from GET /sim/fault-causes for the asset's type (ignored on clear).",
    )
    auto_restore: bool = Field(
        default=False,
        description="A fault clears itself 2-10 min of sim time after injection (no latch).",
    )


class AlarmResetChange(_Change):
    type: Literal["alarm_reset"] = "alarm_reset"
    asset_id: str = Field(description="A BESS or PV id.")


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
    BreakerChange
    | AssetFaultChange
    | AlarmResetChange
    | CommLossChange
    | GridVoltageChange
    | GridFrequencyChange,
    Field(discriminator="type"),
]

# (target, id); the POI meter's id is "".
CommKey = tuple[CommTarget, str]


Key = TypeVar("Key")
Value = TypeVar("Value")


def _frozen(mapping: Mapping[Key, Value]) -> Mapping[Key, Value]:
    return MappingProxyType(dict(mapping))


@dataclass(frozen=True)
class AssetFault:
    since_step: int  # the step it was injected at (it applies from the next one)
    restore_step: int | None = None  # auto-restore: gone before this step is computed
    latched: bool = False  # cleared, but held (FAULT + bits) until an alarm reset


@dataclass(frozen=True)
class FaultClock:
    """What an auto-restore draw needs: the site seed and the step length."""

    seed: int = 0
    step_s: float = 1.0


@dataclass(frozen=True)
class Conditions:
    open_breakers: frozenset[str] = frozenset()
    # asset id → cause → its state
    faults: Mapping[str, Mapping[FaultCause, AssetFault]] = field(
        default_factory=lambda: _frozen({})
    )
    comm_loss: Mapping[CommKey, int] = field(default_factory=lambda: _frozen({}))  # → since step
    grid_vm_pu: float | None = None
    grid_hz: float | None = None

    def comm_lost(self, target: CommTarget, asset_id: str = "") -> bool:
        return (target, asset_id) in self.comm_loss

    def tripped(self, asset_id: str) -> bool:
        """A fault (not a warning) is active or latched on it."""
        return any(SEVERITY[cause] is Severity.FAULT for cause in self.faults.get(asset_id, {}))

    def asserted_causes(self, kind: AssetKind, asset_id: str) -> list[FaultCause]:
        """Its causes whose bits are set (active and latched), in catalog order."""
        return sorted(self.faults.get(asset_id, {}), key=lambda cause: catalog_order(kind, cause))

    def p_max_factor(self, kind: AssetKind, asset_id: str) -> float:
        """The derate its warnings put on its P/S rating (1 = none)."""
        causes = self.faults.get(asset_id, {})
        return min((_factors(kind, cause)[0] for cause in causes), default=1.0)

    def p_available_factor(self, kind: AssetKind, asset_id: str) -> float:
        """PV: the share of its available power its warnings leave (1 = all)."""
        causes = self.faults.get(asset_id, {})
        return min((_factors(kind, cause)[1] for cause in causes), default=1.0)


def _factors(kind: AssetKind, cause: FaultCause) -> tuple[float, float]:
    spec = cause_spec(kind, cause)
    return (spec.p_max_factor, spec.p_available_factor) if spec is not None else (1.0, 1.0)


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
        case AssetFaultChange(asset_id=asset_id, cause=cause, active=active):
            if asset_id in bess_ids:
                allowed = BESS_CAUSES
            elif asset_id in pv_ids:
                allowed = PV_CAUSES
            elif asset_id in asset_ids:
                raise ConditionError(f"{asset_id!r} is a load: only BESS and PV can fault")
            else:
                raise UnknownAssetError(f"no BESS or PV {asset_id!r}")
            if active and cause not in allowed:
                raise ConditionError(
                    f"{cause} doesn't apply to {asset_id!r} (allowed: {sorted(allowed)})"
                )
        case AlarmResetChange(asset_id=asset_id):
            if asset_id in bess_ids | pv_ids:
                pass
            elif asset_id in asset_ids:
                raise ConditionError(f"{asset_id!r} is a load: only BESS and PV have alarms")
            else:
                raise UnknownAssetError(f"no BESS or PV {asset_id!r}")
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


def restore_step(clock: FaultClock, asset_id: str, cause: FaultCause, since_step: int) -> int:
    """When an auto-restore fault injected at `since_step` clears itself: a uniform 2-10 min of
    sim time later, drawn from (seed, asset, cause, step) so a run is reproducible."""
    key = zlib.crc32(f"fault:{asset_id}:{cause}".encode())
    rng = np.random.default_rng((clock.seed, key, since_step))
    duration_s = float(rng.uniform(AUTO_RESTORE_MIN_S, AUTO_RESTORE_MAX_S))
    return since_step + max(1, math.ceil(duration_s / clock.step_s))


def _with_faults(
    conditions: Conditions, asset_id: str, entries: Mapping[FaultCause, AssetFault]
) -> Conditions:
    faults = dict(conditions.faults)
    if entries:
        faults[asset_id] = _frozen(entries)
    else:
        faults.pop(asset_id, None)
    return replace(conditions, faults=_frozen(faults))


def _clear_asset(conditions: Conditions, asset_id: str) -> Conditions:
    """Warnings and auto-restore faults go; the other faults latch."""
    entries = {
        cause: replace(entry, latched=True)
        for cause, entry in conditions.faults.get(asset_id, {}).items()
        if SEVERITY[cause] is Severity.FAULT and entry.restore_step is None
    }
    return _with_faults(conditions, asset_id, entries)


def reset_alarms(conditions: Conditions, asset_id: str) -> Conditions:
    """Drop the asset's latched faults; a cause still injected stays (and keeps it tripped)."""
    entries = {
        cause: entry
        for cause, entry in conditions.faults.get(asset_id, {}).items()
        if not entry.latched
    }
    return _with_faults(conditions, asset_id, entries)


def expire_faults(conditions: Conditions, step_index: int) -> Conditions:
    """Drop the auto-restore faults due by `step_index` (before it is computed)."""

    def due(entry: AssetFault) -> bool:
        return entry.restore_step is not None and entry.restore_step <= step_index

    if not any(due(entry) for entries in conditions.faults.values() for entry in entries.values()):
        return conditions
    faults: dict[str, Mapping[FaultCause, AssetFault]] = {}
    for asset_id, entries in conditions.faults.items():
        kept = {cause: entry for cause, entry in entries.items() if not due(entry)}
        if kept:
            faults[asset_id] = _frozen(kept)
    return replace(conditions, faults=_frozen(faults))


DEFAULT_CLOCK = FaultClock()


def apply_change(
    conditions: Conditions,
    change: ConditionChange,
    step_index: int,
    clock: FaultClock = DEFAULT_CLOCK,
) -> Conditions:
    """The conditions after `change` (already validated). `step_index` is the current step: a
    comm loss records it (it freezes what was published at that step), and so does a fault (an
    auto-restore is drawn from it and `clock`)."""
    match change:
        case BreakerChange(breaker=breaker, closed=closed):
            opened = set(conditions.open_breakers)
            if closed:
                opened.discard(breaker)
            else:
                opened.add(breaker)
            return replace(conditions, open_breakers=frozenset(opened))
        case AssetFaultChange(asset_id=asset_id, active=False):
            return _clear_asset(conditions, asset_id)
        case AssetFaultChange(asset_id=asset_id, cause=cause, auto_restore=auto_restore):
            restore = None
            if auto_restore and SEVERITY[cause] is Severity.FAULT:
                restore = restore_step(clock, asset_id, cause, step_index)
            entries = dict(conditions.faults.get(asset_id, {}))
            entries[cause] = AssetFault(since_step=step_index, restore_step=restore)
            return _with_faults(conditions, asset_id, entries)
        case AlarmResetChange(asset_id=asset_id):
            return reset_alarms(conditions, asset_id)
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
    severity: Severity
    latched: bool = Field(description="Cleared, but held until an alarm_reset.")
    auto_restore: bool
    since_step: int = Field(description="The step it was injected at.")
    restore_step: int | None = Field(description="Auto-restore: gone before this step.")
    restore_sim_time: datetime | None = Field(description="Auto-restore: the sim time it clears.")


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


def summary(
    conditions: Conditions, config: SiteConfig, origin: datetime | None = None
) -> ActiveConditions:
    """`origin` (the sim time of step 0) dates the auto-restores; None leaves them undated."""
    step_s = config.simulation.step_s

    def restore_time(restore: int | None) -> datetime | None:
        if restore is None or origin is None:
            return None
        return origin + timedelta(seconds=restore * step_s)

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
            FaultStatus(
                asset_id=asset_id,
                cause=cause,
                severity=SEVERITY[cause],
                latched=entry.latched,
                auto_restore=entry.restore_step is not None,
                since_step=entry.since_step,
                restore_step=entry.restore_step,
                restore_sim_time=restore_time(entry.restore_step),
            )
            for asset_id, entries in sorted(conditions.faults.items())
            for cause, entry in sorted(entries.items())
        ],
        comm_loss=[
            CommLossStatus(target=target, id=target_id or None, since_step=since)
            for (target, target_id), since in sorted(conditions.comm_loss.items())
        ],
        grid_vm_pu=conditions.grid_vm_pu,
        grid_hz=conditions.grid_hz,
    )
