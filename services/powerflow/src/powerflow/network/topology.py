"""SiteConfig -> Topology: a solver-neutral description of the network.

```
[source] ─ grid impedance (Z = V²/S_sc) ─ [poi]                     (no POI line)
[source] ─ grid impedance ─ [grid] ─ POI line ─ [poi]               (with a POI line)
[poi] ─ feeder line, or a closed switch ─ [col:<id>]                (one per collector)
[col:<id>] ─ step-up transformer ─ [lv:<asset>] ─ BESS/PV (+ BESS aux load)
[poi | col:<id>] ─ (optional transformer ─ [lv:<load>]) ─ site load
```
Breakers: the POI breaker opens the POI branch (the grid side of the POI meter); an asset's
breaker opens its step-up transformer (or, for a load without one, the load itself).
The POI meter is the branch leaving the POI bus toward the grid, oriented from the POI, so its
from-end P/Q is export-positive. Site losses are the transformers and collector feeders: they
exclude the grid equivalent and the POI line, which are on the utility side of the meter.
"""

import math
from dataclasses import dataclass
from enum import StrEnum

from powerflow.site_config.models import (
    POI_BUS_ID,
    LineConfig,
    SiteConfig,
    TransformerConfig,
)

SOURCE_BUS = "source"
GRID_BUS = "grid"
GRID_IMPEDANCE = "grid_equivalent"
POI_LINE = "poi_line"


def collector_bus(collector_id: str) -> str:
    return f"col:{collector_id}"


def lv_bus(asset_id: str) -> str:
    return f"lv:{asset_id}"


def transformer_name(asset_id: str) -> str:
    return f"tx:{asset_id}"


class InjectionKind(StrEnum):
    GENERATOR = "gen"  # generator convention: P > 0 injects
    LOAD = "load"  # load convention: P > 0 consumes


def bess_injection(asset_id: str) -> str:
    return f"bess:{asset_id}"


def bess_aux_injection(asset_id: str) -> str:
    return f"bess_aux:{asset_id}"


def pv_injection(asset_id: str) -> str:
    return f"pv:{asset_id}"


def load_injection(asset_id: str) -> str:
    return f"load:{asset_id}"


@dataclass(frozen=True)
class BusSpec:
    name: str
    vn_kv: float


@dataclass(frozen=True)
class SlackSpec:
    bus: str
    vm_pu: float
    va_degree: float
    sc_mva: float
    x_r: float


@dataclass(frozen=True)
class ImpedanceSpec:
    name: str
    from_bus: str
    to_bus: str
    r_ohm: float
    x_ohm: float
    vn_kv: float


@dataclass(frozen=True)
class LineSpec:
    name: str
    from_bus: str
    to_bus: str
    length_km: float
    r_ohm_per_km: float
    x_ohm_per_km: float
    c_nf_per_km: float
    max_i_ka: float


@dataclass(frozen=True)
class SwitchSpec:
    name: str
    bus: str
    other_bus: str


@dataclass(frozen=True)
class TransformerSpec:
    name: str
    hv_bus: str
    lv_bus: str
    sn_kva: float
    vn_hv_kv: float
    vn_lv_kv: float
    vk_pct: float
    vkr_pct: float
    pfe_kw: float
    i0_pct: float


@dataclass(frozen=True)
class InjectionSpec:
    name: str
    bus: str
    kind: InjectionKind


class PoiBranchKind(StrEnum):
    IMPEDANCE = "impedance"
    LINE = "line"


class BreakerElement(StrEnum):
    """The element a breaker takes out of service when it opens."""

    TRANSFORMER = "transformer"
    IMPEDANCE = "impedance"
    LINE = "line"
    INJECTION = "injection"


@dataclass(frozen=True)
class BreakerSpec:
    name: str  # the asset id, or "poi"
    element_kind: BreakerElement
    element: str  # the TransformerSpec / ImpedanceSpec / LineSpec / InjectionSpec name
    closed: bool  # initial position, from the site config


@dataclass(frozen=True)
class Topology:
    buses: tuple[BusSpec, ...]
    slack: SlackSpec
    impedances: tuple[ImpedanceSpec, ...]
    lines: tuple[LineSpec, ...]
    switches: tuple[SwitchSpec, ...]
    transformers: tuple[TransformerSpec, ...]
    injections: tuple[InjectionSpec, ...]
    poi_bus: str
    poi_branch: str
    poi_branch_kind: PoiBranchKind
    # Branches whose losses count as site losses (inside the POI meter).
    site_lines: tuple[str, ...]
    breakers: tuple[BreakerSpec, ...] = ()

    def bus(self, name: str) -> BusSpec:
        return next(bus for bus in self.buses if bus.name == name)


def grid_impedance_ohm(vn_kv: float, sc_mva: float, x_r: float) -> tuple[float, float]:
    """Thevenin source impedance from the short-circuit power: |Z| = V²/S_sc, split by X/R."""
    z_ohm = vn_kv**2 / sc_mva
    r_ohm = z_ohm / math.sqrt(1 + x_r**2)
    return r_ohm, r_ohm * x_r


def resistive_percent(z_pct: float, x_r: float) -> float:
    """vkr% (the resistive part of %Z) from %Z and X/R."""
    return z_pct / math.sqrt(1 + x_r**2)


def _line(name: str, from_bus: str, to_bus: str, line: LineConfig) -> LineSpec:
    return LineSpec(
        name=name,
        from_bus=from_bus,
        to_bus=to_bus,
        length_km=line.length_km,
        r_ohm_per_km=line.r_ohm_per_km,
        x_ohm_per_km=line.x_ohm_per_km,
        c_nf_per_km=line.c_nf_per_km,
        max_i_ka=line.max_i_ka,
    )


def _transformer(asset_id: str, hv_bus: str, config: TransformerConfig) -> TransformerSpec:
    return TransformerSpec(
        name=transformer_name(asset_id),
        hv_bus=hv_bus,
        lv_bus=lv_bus(asset_id),
        sn_kva=config.s_rated_kva,
        vn_hv_kv=config.vn_hv_kv,
        vn_lv_kv=config.vn_lv_kv,
        vk_pct=config.z_pct,
        vkr_pct=resistive_percent(config.z_pct, config.x_r),
        pfe_kw=config.no_load_loss_kw,
        i0_pct=config.i0_pct,
    )


def build_topology(config: SiteConfig) -> Topology:
    grid_kv = config.grid.vn_kv
    buses = [BusSpec(SOURCE_BUS, grid_kv), BusSpec(POI_BUS_ID, grid_kv)]
    lines: list[LineSpec] = []
    switches: list[SwitchSpec] = []
    transformers: list[TransformerSpec] = []
    injections: list[InjectionSpec] = []
    site_lines: list[str] = []
    breakers: list[BreakerSpec] = []

    r_ohm, x_ohm = grid_impedance_ohm(grid_kv, config.grid.sc_mva, config.grid.x_r)
    if config.poi.line is None:
        impedance = ImpedanceSpec(GRID_IMPEDANCE, POI_BUS_ID, SOURCE_BUS, r_ohm, x_ohm, grid_kv)
        poi_branch, poi_branch_kind = GRID_IMPEDANCE, PoiBranchKind.IMPEDANCE
    else:
        buses.append(BusSpec(GRID_BUS, grid_kv))
        impedance = ImpedanceSpec(GRID_IMPEDANCE, GRID_BUS, SOURCE_BUS, r_ohm, x_ohm, grid_kv)
        lines.append(_line(POI_LINE, POI_BUS_ID, GRID_BUS, config.poi.line))
        poi_branch, poi_branch_kind = POI_LINE, PoiBranchKind.LINE
    poi_element = (
        BreakerElement.LINE if poi_branch_kind is PoiBranchKind.LINE else BreakerElement.IMPEDANCE
    )
    breakers.append(BreakerSpec(POI_BUS_ID, poi_element, poi_branch, config.poi.breaker.closed))

    for collector in config.collectors:
        bus_name = collector_bus(collector.id)
        buses.append(BusSpec(bus_name, grid_kv))
        if collector.feeder is None:
            switches.append(SwitchSpec(f"sw:{collector.id}", POI_BUS_ID, bus_name))
        else:
            feeder_name = f"feeder:{collector.id}"
            lines.append(_line(feeder_name, bus_name, POI_BUS_ID, collector.feeder))
            site_lines.append(feeder_name)

    for bess in config.bess:
        buses.append(BusSpec(lv_bus(bess.id), bess.transformer.vn_lv_kv))
        transformers.append(_transformer(bess.id, collector_bus(bess.collector), bess.transformer))
        injections.append(
            InjectionSpec(bess_injection(bess.id), lv_bus(bess.id), InjectionKind.GENERATOR)
        )
        injections.append(
            InjectionSpec(bess_aux_injection(bess.id), lv_bus(bess.id), InjectionKind.LOAD)
        )
        breakers.append(
            BreakerSpec(
                bess.id, BreakerElement.TRANSFORMER, transformer_name(bess.id), bess.breaker.closed
            )
        )
    for pv in config.pv:
        buses.append(BusSpec(lv_bus(pv.id), pv.transformer.vn_lv_kv))
        transformers.append(_transformer(pv.id, collector_bus(pv.collector), pv.transformer))
        injections.append(
            InjectionSpec(pv_injection(pv.id), lv_bus(pv.id), InjectionKind.GENERATOR)
        )
        breakers.append(
            BreakerSpec(
                pv.id, BreakerElement.TRANSFORMER, transformer_name(pv.id), pv.breaker.closed
            )
        )
    for load in config.loads:
        mv_bus = POI_BUS_ID if load.bus == POI_BUS_ID else collector_bus(load.bus)
        load_bus = mv_bus
        if load.transformer is not None:
            buses.append(BusSpec(lv_bus(load.id), load.transformer.vn_lv_kv))
            transformers.append(_transformer(load.id, mv_bus, load.transformer))
            load_bus = lv_bus(load.id)
        injections.append(InjectionSpec(load_injection(load.id), load_bus, InjectionKind.LOAD))
        if load.transformer is not None:
            element = BreakerSpec(
                load.id, BreakerElement.TRANSFORMER, transformer_name(load.id), load.breaker.closed
            )
        else:
            element = BreakerSpec(
                load.id, BreakerElement.INJECTION, load_injection(load.id), load.breaker.closed
            )
        breakers.append(element)

    return Topology(
        buses=tuple(buses),
        slack=SlackSpec(
            bus=SOURCE_BUS,
            vm_pu=config.grid.vm_pu,
            va_degree=config.grid.va_degree,
            sc_mva=config.grid.sc_mva,
            x_r=config.grid.x_r,
        ),
        impedances=(impedance,),
        lines=tuple(lines),
        switches=tuple(switches),
        transformers=tuple(transformers),
        injections=tuple(injections),
        poi_bus=POI_BUS_ID,
        poi_branch=poi_branch,
        poi_branch_kind=poi_branch_kind,
        site_lines=tuple(site_lines),
        breakers=tuple(breakers),
    )
