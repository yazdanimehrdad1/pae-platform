"""Build a dev seed from one of powerflow's simulated sites, as if it were a real site.

powerflow publishes its default sites' topology (`contracts/powerflow/sites.json`) and the
register layout of its Modbus server (`contracts/modbus/powerflow.registers.json`), both
generated there by `make contract`. Seeding from those two files means backend-ot polls exactly
what powerflow serves, with nothing to keep in sync by hand. The services share only the files.

Mapping (one backend-ot device per point-standard device of the site):

    device kind             -> type: site RTAC (plant controller), bess BESS, pv PV,
                               load IED, poi_meter / feeder_meter METER
    powerflow Modbus server -> host "powerflow" (compose DNS), port 502, unit id 1, direct
                               reads (not the aggregator), zero-based addresses
    served register         -> NATIVE point: address = device base + offset, the standard name,
    (yes / calc)               data type, scale, SI unit, enum/bit labels, holding table,
                               big-endian msw-first. Unserved ("no") rows always read 0: skipped.
    topology                -> the site (no profile) and its single line diagram

The site is the shipped default; edits made to it in powerflow's database aren't seen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from schemas.api_models import (
    Location,
    SiteCreateRequest,
    SiteSld,
    SldBus,
    SldConnection,
    SldDeviceLink,
    SldNode,
)
from schemas.api_models.requests import DeviceCreateRequest, DevicePointCreateRequest
from schemas.api_models.single_line_diagram import SldRole
from schemas.api_models.types import DeviceType, PointClass, register_size
from schemas.tests_models import (
    DeviceIdResolver,
    PointIdResolver,
    PowerflowRegister,
    PowerflowRegistersContract,
    PowerflowSite,
    PowerflowSitesContract,
    SeedData,
    SeedDevice,
)
from schemas.tests_models.powerflow_contract import (
    PowerflowBess,
    PowerflowCollector,
    PowerflowDeviceKind,
    PowerflowDeviceRef,
    PowerflowLoad,
    PowerflowPv,
)

REGISTERS_CONTRACT = ("modbus", "powerflow.registers.json")
SITES_CONTRACT = ("powerflow", "sites.json")

# powerflow's Modbus server on the compose network (container port; 1502 on the dev host).
POWERFLOW_HOST = "powerflow"

DEVICE_TYPES: dict[PowerflowDeviceKind, DeviceType] = {
    "site": "RTAC",
    "met_station": "IED",
    "bess": "BESS",
    "pv": "PV",
    "load": "IED",
    "poi_meter": "METER",
    "feeder_meter": "METER",
}
# Device-name suffix for the kinds whose powerflow id isn't descriptive.
_NAME_BY_KIND: dict[PowerflowDeviceKind, str] = {
    "site": "plant_controller",
    "met_station": "met_station",
    "poi_meter": "poi_meter",
}
KIND_LABELS: dict[PowerflowDeviceKind, str] = {
    "site": "plant controller",
    "met_station": "met station",
    "bess": "BESS",
    "pv": "PV inverter",
    "load": "load",
    "poi_meter": "POI meter",
    "feeder_meter": "feeder meter",
}
AssetKind = Literal["bess", "pv", "load"]
METER_ROLES: dict[SldRole, str] = {
    "vab": "PhVphAB", "vbc": "PhVphBC", "vca": "PhVphCA",
    "ia": "AphA", "ib": "AphB", "ic": "AphC", "in": "AN",
}
BESS_ROLES: dict[SldRole, str] = {"soc": "SoC", "power": "W", "mode": "InvSt"}
PV_ROLES: dict[SldRole, str] = {"power": "W"}
ASSET_ROLES: dict[AssetKind, dict[SldRole, str]] = {"bess": BESS_ROLES, "pv": PV_ROLES}


def default_contract_path(parts: tuple[str, str]) -> Path:
    """Where the seeder finds a powerflow contract: next to this file (copied in by
    `make seed-db-powerflow`), else the monorepo's `contracts/` (on the host)."""
    here = Path(__file__).resolve()
    sibling = here.parent / parts[1]
    if sibling.exists():
        return sibling
    if len(here.parents) > 4:
        repo_contract = here.parents[4] / "contracts" / parts[0] / parts[1]
        if repo_contract.exists():
            return repo_contract
    raise FileNotFoundError(
        f"{parts[1]} not found next to {here.name} or in the monorepo contracts/ directory; "
        "generate it with `make -C services/powerflow contract`"
    )


def load_registers(path: Path) -> PowerflowRegistersContract:
    return PowerflowRegistersContract.model_validate_json(path.read_bytes())


def load_sites(path: Path) -> PowerflowSitesContract:
    return PowerflowSitesContract.model_validate_json(path.read_bytes())


def site_display_name(site_key: str) -> str:
    """"2bess_1pv" -> "Powerflow 2BESS 1PV"."""
    return "Powerflow " + " ".join(part.upper() for part in site_key.split("_"))


def device_name(site_key: str, device: PowerflowDeviceRef) -> str:
    return f"{site_key}-{_NAME_BY_KIND.get(device.kind, device.asset_id)}"


def point_class(register: PowerflowRegister) -> PointClass:
    if register.data_type.startswith("bitfield"):
        return "ALARM"
    if register.data_type.startswith("enum"):
        return "BINARY"
    return "ANALOG"


def build_point(register: PowerflowRegister, base: int) -> DevicePointCreateRequest:
    point_kind = point_class(register)
    return DevicePointCreateRequest(
        address=base + register.offset,
        name=register.point,
        poll_kind="holding",
        data_type=register.data_type,
        size=register_size(register.data_type),
        scale_factor=register.scale,
        unit=register.unit or None,
        byte_order="big-endian",
        word_order="msw_first",
        enum_detail=register.enum_detail,
        bitfield_detail=register.bitfield_detail,
        point_class=point_kind,
        severity="LOW" if point_kind == "ALARM" else None,
    )


def _capacity(site: PowerflowSite) -> str:
    bess_mw = sum(bess.p_discharge_max_kw for bess in site.bess) / 1000
    bess_mwh = sum(bess.capacity_kwh for bess in site.bess) / 1000
    pv_mw = sum(pv.p_max_kw for pv in site.pv) / 1000
    parts = []
    if site.bess:
        parts.append(f"{bess_mw:g} MW / {bess_mwh:g} MWh BESS")
    if site.pv:
        parts.append(f"{pv_mw:g} MWac PV")
    return " + ".join(parts) or "n/a"


def build_site(site_key: str, site: PowerflowSite) -> SiteCreateRequest:
    return SiteCreateRequest(
        client_id="powerflow-sim",
        name=site_display_name(site_key),
        location=Location(street="Simulated (powerflow)", city="n/a", state="n/a", zip_code=0),
        operator="PAE (simulated)",
        capacity=_capacity(site),
        description=(
            f"{site.display_name}. Simulated by powerflow (site {site_key}); seeded from "
            "contracts/powerflow/sites.json and contracts/modbus/powerflow.registers.json"
        ),
        profile=None,
    )


def build_device(site_key: str, device: PowerflowDeviceRef, registers: PowerflowRegistersContract,
                 site_name: str) -> SeedDevice:
    return SeedDevice(
        site_name=site_name,
        device=DeviceCreateRequest(
            name=device_name(site_key, device),
            type=DEVICE_TYPES[device.kind],
            protocol="Modbus",
            vendor="powerflow (simulated)",
            model=device.kind,
            host=POWERFLOW_HOST,
            port=registers.port,
            timeout=5.0,
            server_address=registers.unit_id,
            description=(
                f"Simulated {KIND_LABELS[device.kind]} {device.asset_id} of powerflow site "
                f"{site_key}; Modbus registers {device.base}..{device.base + registers.chunk_registers - 1}"
            ),
            poll_enabled=True,
            read_from_aggregator=False,
            modbus_address_mode="zero_based",
        ),
    )


def _kv(value: float) -> str:
    return f"{value:g} kV"


def _transformer_rating(s_rated_kva: float, vn_hv_kv: float, vn_lv_kv: float) -> str:
    return f"{s_rated_kva / 1000:g} MVA {vn_hv_kv:g}/{vn_lv_kv:g} kV"


def build_sld(site_key: str, site: PowerflowSite, point_id: PointIdResolver,
              device_id: DeviceIdResolver) -> SiteSld:
    """The site's single line diagram, top to bottom the way powerflow builds its network:
    utility, POI (line), POI meter and breaker, POI bus (and loads on it), each collector's tie
    and bus, then per asset its feeder meter, breaker, step-up transformer and the asset."""
    devices = {(device.kind, device.asset_id): device for device in site.devices}
    meters_by_asset = {meter.asset: meter for meter in site.meters}

    def link(kind: PowerflowDeviceKind, asset_id: str, roles: dict[SldRole, str]) -> SldDeviceLink:
        name = device_name(site_key, devices[(kind, asset_id)])
        return SldDeviceLink(
            device_id=device_id(name),
            points={role: point_id(name, point) for role, point in roles.items()},
        )

    nodes: list[SldNode] = []
    buses: list[SldBus] = []
    connections: list[SldConnection] = []

    def connect(*chain: str) -> None:
        connections.extend(SldConnection(from_id=a, to_id=b) for a, b in zip(chain, chain[1:], strict=False))

    poi_loads = [load for load in site.loads if load.bus == "poi"]
    groups: list[tuple[PowerflowCollector, list[tuple[AssetKind, PowerflowBess | PowerflowPv | PowerflowLoad]]]] = [
        (
            collector,
            [("bess", item) for item in site.bess if item.collector == collector.id]
            + [("pv", item) for item in site.pv if item.collector == collector.id]
            + [("load", item) for item in site.loads if item.bus == collector.id],
        )
        for collector in site.collectors
    ]
    columns = len(poi_loads) + sum(max(len(assets), 1) for _, assets in groups)
    centre = (columns - 1) / 2
    grid_kv = _kv(site.grid.vn_kv)

    nodes.append(SldNode(id="utility", type="grid", name="Utility", voltage=grid_kv,
                         rating=f"Ssc {site.grid.sc_mva:g} MVA", col=centre, row=0))
    nodes.append(SldNode(id="poi", type="poi", name="POI (line)" if site.poi.has_line else "POI",
                         voltage=grid_kv, col=centre, row=1))
    nodes.append(SldNode(id="poi_meter", type="meter", name="POI meter", voltage=grid_kv, col=centre, row=2,
                         device=link("poi_meter", "meter", METER_ROLES)))
    nodes.append(SldNode(id="poi_breaker", type="breaker", name="POI breaker", col=centre, row=3))
    buses.append(SldBus(id="poi_bus", name="POI bus", voltage=grid_kv, row=4,
                        col_start=-0.5, col_end=columns - 0.5))
    connect("utility", "poi", "poi_meter", "poi_breaker", "poi_bus")
    plant_device = devices.get(("site", "site"))
    if plant_device is not None:
        nodes.append(SldNode(id="plant_controller", type="plant_controller", name="Plant controller",
                             col=centre + 1.5, row=2))

    def asset_column(kind: AssetKind, asset_id: str, name: str, column: float, top: str, top_row: float,
                     transformer: tuple[float, float, float] | None, rating: str) -> None:
        chain = [top]
        row = top_row + 1
        meter = meters_by_asset.get(asset_id)
        if meter is not None:
            nodes.append(SldNode(id=f"meter_{meter.id}", type="meter", name=meter.name, col=column, row=row,
                                 device=link("feeder_meter", meter.id, METER_ROLES)))
            chain.append(f"meter_{meter.id}")
        row += 1
        nodes.append(SldNode(id=f"brk_{asset_id}", type="breaker", name=f"{name} breaker", col=column, row=row))
        chain.append(f"brk_{asset_id}")
        row += 1
        if transformer is not None:
            nodes.append(SldNode(id=f"tx_{asset_id}", type="transformer", name=f"tx {asset_id}",
                                 rating=_transformer_rating(*transformer), col=column, row=row))
            chain.append(f"tx_{asset_id}")
        row += 1
        roles = ASSET_ROLES.get(kind)
        nodes.append(SldNode(
            id=asset_id, type=kind, name=name, rating=rating, col=column, row=row,
            device=link(kind, asset_id, roles) if roles else None,
        ))
        chain.append(asset_id)
        connect(*chain)

    column = 0
    for load in poi_loads:
        transformer = load.transformer
        asset_column("load", load.id, load.name, column, "poi_bus", 4,
                     (transformer.s_rated_kva, transformer.vn_hv_kv, transformer.vn_lv_kv) if transformer else None,
                     "load")
        column += 1

    for collector, assets in groups:
        span = max(len(assets), 1)
        middle = column + (span - 1) / 2
        tie = f"tie_{collector.id}"
        nodes.append(SldNode(id=tie, type="switch",
                             name=f"{collector.id} feeder" if collector.has_feeder else f"{collector.id} tie",
                             col=middle, row=5))
        bus = f"bus_{collector.id}"
        buses.append(SldBus(id=bus, name=f"{collector.id} bus", voltage=grid_kv, row=6,
                            col_start=column - 0.5, col_end=column + span - 0.5))
        connect("poi_bus", tie, bus)
        for index, (kind, item) in enumerate(assets):
            transformer = item.transformer
            if isinstance(item, PowerflowBess):
                rating = f"{item.p_discharge_max_kw / 1000:g} MW / {item.capacity_kwh / 1000:g} MWh"
            elif isinstance(item, PowerflowPv):
                rating = f"{item.p_max_kw / 1000:g} MWac / {item.dc_kwp / 1000:g} MWp"
            else:
                rating = "load"
            asset_column(kind, item.id, item.name, column + index, bus, 6,
                         (transformer.s_rated_kva, transformer.vn_hv_kv, transformer.vn_lv_kv)
                         if transformer else None, rating)
        column += span

    return SiteSld(schema_version=1, nodes=tuple(nodes), buses=tuple(buses), connections=tuple(connections))


def build_seed(site_key: str, registers: PowerflowRegistersContract,
               sites: PowerflowSitesContract) -> SeedData:
    """The seed for one of powerflow's default sites (e.g. "2bess_1pv")."""
    if site_key not in sites.sites:
        raise ValueError(f"powerflow has no default site {site_key!r} (sites: {sorted(sites.sites)})")
    site = sites.sites[site_key]
    site_request = build_site(site_key, site)
    devices = [build_device(site_key, device, registers, site_request.name) for device in site.devices]
    points = {
        device_name(site_key, device): [
            build_point(register, device.base)
            for register in registers.device_types[device.kind].registers
            if register.powerflow_server != "no"
        ]
        for device in site.devices
    }
    return SeedData(
        sites=[site_request],
        devices=devices,
        device_points=points,
        site_slds=lambda point_id, device_id: {
            site_request.name: build_sld(site_key, site, point_id, device_id)
        },
    )


def powerflow_seed_data(site_key: str) -> SeedData:
    return build_seed(
        site_key,
        load_registers(default_contract_path(REGISTERS_CONTRACT)),
        load_sites(default_contract_path(SITES_CONTRACT)),
    )
