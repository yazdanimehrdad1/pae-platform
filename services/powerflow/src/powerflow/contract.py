"""The published contracts, rendered for `contracts/`: the OpenAPI spec and the point lists."""

import json

from fastapi import FastAPI

from powerflow.points import POINT_LISTS

POINTS_CONTRACT_VERSION = 1


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
