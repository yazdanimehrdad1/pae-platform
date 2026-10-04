"""The published contracts, rendered for `contracts/`: the OpenAPI spec, the point lists and the
Modbus server's register layout."""

import json

from fastapi import FastAPI

from powerflow.point_standard import (
    CHUNK_REGISTERS,
    POINT_LIST_FILE,
    DeviceKind,
    PointStandard,
    build_layout,
    device_template,
)
from powerflow.points import POINT_LISTS
from powerflow.settings import DEFAULT_MODBUS_PORT, DEFAULT_MODBUS_UNIT_ID
from powerflow.site_config import SiteConfig

POINTS_CONTRACT_VERSION = 1
# Breaking: a moved offset or base, a removed point, or a changed type, scale or unit.
REGISTERS_CONTRACT_VERSION = 1


def _dump(document: object) -> str:
    """Deterministic JSON text: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def render_openapi_contract(app: FastAPI) -> str:
    return _dump(app.openapi())


def render_points_contract() -> str:
    """The protocol-neutral point lists that protocol maps (Modbus, DNP3) and the EMS bind to."""
    return _dump(
        {
            "contract": "powerflow/points",
            "version": POINTS_CONTRACT_VERSION,
            "naming": "<asset_type>.<asset_id>.<point>; poi uses asset_id 'meter', site 'sim', "
            "meter (feeder meters) the meter id",
            "scale": "engineering value = raw register value × scale (scale_hint)",
            "point_lists": {
                str(asset_type): [point.model_dump(mode="json") for point in points]
                for asset_type, points in POINT_LISTS.items()
            },
        }
    )


GROUPS = [
    {
        "group": "site",
        "base": 0,
        "devices": "site at 0; met_station at 100 if a PV uses irradiance",
    },
    {"group": "bess", "base": 1000, "devices": "bess n at 1000 + 100·(n−1)"},
    {"group": "pv", "base": 2000, "devices": "pv n at 2000 + 100·(n−1)"},
    {"group": "gen_load", "base": 3000, "devices": "load n at 3000 + 100·(n−1)"},
    {
        "group": "meter",
        "base": 4000,
        "devices": "poi_meter at 4000, feeder_meter n at 4000 + 100·n",
    },
]


def render_registers_contract(standard: PointStandard, sites: dict[str, SiteConfig]) -> str:
    """The Modbus server's register layout: a register template per device kind (offsets from
    the device base) and where each shipped default site puts its devices."""
    return _dump(
        {
            "$comment": "GENERATED from services/powerflow/docs/point-standard/*.csv "
            "(device_types) and the default-sites migration (default_sites) by "
            "`make -C services/powerflow contract`. Do not edit by hand. default_sites covers "
            "the shipped defaults only: a running site's bases follow its stored config "
            "(GET /api/modbus/registers).",
            "contract": "powerflow/modbus-registers",
            "version": REGISTERS_CONTRACT_VERSION,
            "register_numbering": "zero_based",
            "register_tables": "holding (FC03) and input (FC04) return the same values; "
            "read-only (writes get exception 1)",
            "port": DEFAULT_MODBUS_PORT,
            "port_note": "container port; the dev stack publishes it on host port 1502",
            "unit_id": DEFAULT_MODBUS_UNIT_ID,
            "chunk_registers": CHUNK_REGISTERS,
            "address": "device base + register offset",
            "groups": GROUPS,
            "device_types": {
                str(kind): {
                    "point_list": POINT_LIST_FILE[kind],
                    "registers": [
                        {
                            "offset": register.address,
                            "point": register.row.point,
                            "data_type": register.row.data_type,
                            "width": register.row.width,
                            "signed": register.row.signed,
                            "scale": register.row.scale,
                            "unit": register.row.unit,
                            "powerflow_server": str(register.row.support),
                            "enum_detail": register.row.enum_detail,
                            "bitfield_detail": register.row.bitfield_detail,
                        }
                        for register in device_template(standard, kind)
                    ],
                }
                for kind in DeviceKind
            },
            "default_sites": {
                name: [
                    {"kind": str(device.kind), "asset_id": device.asset_id, "base": device.base}
                    for device in build_layout(config, standard)
                ]
                for name, config in sorted(sites.items())
            },
        }
    )
