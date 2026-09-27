"""Configuration: /sites (+ their /modbus-maps), /profiles, /schemas, /defaults.

Sites, their Modbus maps and the active site are stored in Postgres. Profile scenarios are CSV
files for now. The JSON Schemas come from code. The shipped site_config/ files are only defaults,
seeded into an empty database. Every write is validated before it's stored.
"""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import JsonValue

from powerflow.core.site_library import (
    DefaultsInfo,
    DefaultsRestoreResult,
    ModbusMapSummary,
    ProfileSaveResult,
    ProfileScenarios,
    SiteList,
)
from powerflow.interfaces.base import AdapterContext, AdapterRegistry
from powerflow.interfaces.http.dependencies import get_adapters, get_context
from powerflow.interfaces.http.schemas import ErrorResponse, OpenApiResponses
from powerflow.points.modbus_map import ModbusMap
from powerflow.site_config import SiteConfig
from powerflow.storage import ProfileFolder

router = APIRouter()
ERRORS: OpenApiResponses = {
    404: {"model": ErrorResponse, "description": "No such site, map or scenario."},
    409: {"model": ErrorResponse, "description": "Not allowed now (running, or in use)."},
    422: {"model": ErrorResponse, "description": "Invalid name or content."},
}
CSV_BODY = {
    "requestBody": {
        "required": True,
        "content": {"text/csv": {"schema": {"type": "string"}}},
        "description": "Load: timestamp,p_kw,q_kvar (or timestamp,p_kw,pf). PV: timestamp and "
        "p_kw (ac_kw source) and/or ghi_wm2 (irradiance source). Timestamps ISO 8601.",
    }
}
CSV_RESPONSE: OpenApiResponses = {
    **ERRORS,
    200: {"content": {"text/csv": {"schema": {"type": "string"}}}},
}


# -- sites -------------------------------------------------------------------------------


@router.get("/sites", response_model=SiteList, tags=["sites"], summary="Stored sites")
async def list_sites(context: AdapterContext = Depends(get_context)) -> SiteList:
    return await context.library.list_sites()


@router.get("/sites/{name}", response_model=SiteConfig, responses=ERRORS, tags=["sites"])
async def get_site(name: str, context: AdapterContext = Depends(get_context)) -> SiteConfig:
    return await context.library.get_site(name)


@router.put(
    "/sites/{name}",
    response_model=SiteConfig,
    responses=ERRORS,
    tags=["sites"],
    summary="Create or replace a stored site",
    description="Validated (schema, references, profile scenarios exist) before it's written. "
    "Saving the active site reloads it, so the simulation must be stopped (409 otherwise).",
)
async def put_site(
    name: str, config: SiteConfig, context: AdapterContext = Depends(get_context)
) -> SiteConfig:
    return await context.library.save_site(name, config)


@router.delete(
    "/sites/{name}", status_code=204, responses=ERRORS, tags=["sites"], summary="Delete a site"
)
async def delete_site(name: str, context: AdapterContext = Depends(get_context)) -> Response:
    await context.library.delete_site(name)
    return Response(status_code=204)


@router.post(
    "/sites/{name}/activate",
    response_model=SiteConfig,
    responses=ERRORS,
    tags=["sites"],
    summary="Load a stored site (only while stopped)",
    description="Rebuilds the network, resets the simulation and records the site as the one "
    "to load at startup. The engine stays stopped: POST /api/sim/start.",
)
async def activate_site(
    name: str,
    context: AdapterContext = Depends(get_context),
    adapters: AdapterRegistry = Depends(get_adapters),
) -> SiteConfig:
    config = await context.library.activate(name)
    await adapters.stop_all()
    await adapters.start_enabled(config.interfaces, context)
    return config


# -- Modbus maps (per site) ---------------------------------------------------------------


@router.get(
    "/sites/{site}/modbus-maps",
    response_model=list[ModbusMapSummary],
    responses=ERRORS,
    tags=["modbus maps"],
    summary="A site's per-asset Modbus maps",
)
async def list_maps(
    site: str, context: AdapterContext = Depends(get_context)
) -> list[ModbusMapSummary]:
    return await context.library.list_maps(site)


@router.get(
    "/sites/{site}/modbus-maps/{asset}",
    response_model=ModbusMap,
    responses=ERRORS,
    tags=["modbus maps"],
    summary="One asset's map (asset = <asset_type>.<asset_id>, e.g. pv.pv1, poi.meter)",
)
async def get_map(
    site: str, asset: str, context: AdapterContext = Depends(get_context)
) -> ModbusMap:
    return await context.library.get_map(site, asset)


@router.put(
    "/sites/{site}/modbus-maps/{asset}",
    response_model=ModbusMap,
    responses=ERRORS,
    tags=["modbus maps"],
    summary="Create or replace an asset's map",
    description="Rejected (422) if the site has no such asset, the body's `asset` differs from "
    "the path, registers overlap, a point isn't in the asset type's point list, a writable "
    "point isn't on a holding register/coil (or vice versa), or the unit_id+port is already "
    "used by another map of the site.",
)
async def put_map(
    site: str,
    asset: str,
    modbus_map: ModbusMap,
    context: AdapterContext = Depends(get_context),
) -> ModbusMap:
    return await context.library.save_map(site, asset, modbus_map)


@router.delete(
    "/sites/{site}/modbus-maps/{asset}",
    status_code=204,
    responses=ERRORS,
    tags=["modbus maps"],
    summary="Delete an asset's map",
)
async def delete_map(
    site: str, asset: str, context: AdapterContext = Depends(get_context)
) -> Response:
    await context.library.delete_map(site, asset)
    return Response(status_code=204)


# -- profiles ----------------------------------------------------------------------------


@router.get(
    "/profiles",
    response_model=ProfileScenarios,
    tags=["profiles"],
    summary="Profile scenarios",
)
async def list_profiles(context: AdapterContext = Depends(get_context)) -> ProfileScenarios:
    return context.library.list_profiles()


@router.get(
    "/profiles/{folder}/{scenario}",
    responses=CSV_RESPONSE,
    tags=["profiles"],
    summary="A profile scenario's CSV",
    response_class=Response,
)
async def get_profile(
    folder: ProfileFolder, scenario: str, context: AdapterContext = Depends(get_context)
) -> Response:
    return Response(content=context.library.read_profile(folder, scenario), media_type="text/csv")


@router.put(
    "/profiles/{folder}/{scenario}",
    response_model=ProfileSaveResult,
    responses=ERRORS,
    openapi_extra=CSV_BODY,
    tags=["profiles"],
    summary="Create or replace a profile scenario (CSV body)",
    description="Validated before it's written. Active-site assets using the scenario pick it "
    "up on the next step, even while running (their configured scale/loop still apply).",
)
async def put_profile(
    folder: ProfileFolder,
    scenario: str,
    request: Request,
    context: AdapterContext = Depends(get_context),
) -> ProfileSaveResult:
    text = (await request.body()).decode("utf-8", errors="replace")
    return await context.library.save_profile(folder, scenario, text)


@router.delete(
    "/profiles/{folder}/{scenario}",
    status_code=204,
    responses=ERRORS,
    tags=["profiles"],
    summary="Delete a profile scenario (409 while any stored site uses it)",
)
async def delete_profile(
    folder: ProfileFolder, scenario: str, context: AdapterContext = Depends(get_context)
) -> Response:
    await context.library.delete_profile(folder, scenario)
    return Response(status_code=204)


# -- schemas (generated from the Pydantic models; read-only) -----------------------------


@router.get("/schemas", response_model=list[str], tags=["schemas"], summary="Stored JSON Schemas")
async def list_schemas(context: AdapterContext = Depends(get_context)) -> list[str]:
    return context.library.list_schemas()


@router.get(
    "/schemas/{name}",
    response_model=dict[str, JsonValue],
    responses=ERRORS,
    tags=["schemas"],
    summary="One JSON Schema, e.g. site-config or modbus-map",
)
async def get_schema(
    name: str, context: AdapterContext = Depends(get_context)
) -> dict[str, JsonValue]:
    return context.library.get_schema(name)


# -- defaults (site_config/, a read-only seed) ---------------------------------------------


@router.get(
    "/defaults",
    response_model=DefaultsInfo,
    tags=["defaults"],
    summary="The shipped default sites and Modbus maps",
    description="Seeded into an empty database at startup. Restore them with "
    "POST /api/defaults/restore.",
)
async def get_defaults(context: AdapterContext = Depends(get_context)) -> DefaultsInfo:
    return context.library.defaults_info()


@router.post(
    "/defaults/restore",
    response_model=DefaultsRestoreResult,
    responses=ERRORS,
    tags=["defaults"],
    summary="Import the default sites and maps into the database",
    description="Without overwrite, sites and maps already stored are kept (reported as "
    "skipped). With overwrite=true they're replaced; the simulation must be stopped (409), "
    "and the active site is reloaded if it was replaced. The active-site choice is unchanged.",
)
async def restore_defaults(
    overwrite: bool = False, context: AdapterContext = Depends(get_context)
) -> DefaultsRestoreResult:
    return await context.library.restore_defaults(overwrite)
