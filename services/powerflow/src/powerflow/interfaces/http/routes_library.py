"""Configuration: /sites, /profiles, /schemas.

Sites and the active site are stored in Postgres, the only store for them (a fresh database gets
the default sites from a data migration). Profile scenarios are CSV files. The JSON Schema comes
from code. Every write is validated before it's stored.
"""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import JsonValue

from powerflow.core.site_library import ProfileSaveResult, ProfileScenarios, SiteList
from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.interfaces.http.schemas import ErrorResponse, OpenApiResponses
from powerflow.site_config import SiteConfig
from powerflow.storage import ProfileFolder

router = APIRouter()
ERRORS: OpenApiResponses = {
    404: {"model": ErrorResponse, "description": "No such site or scenario."},
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
    "Saving the active site reloads it and restarts its protocol interfaces, so the simulation "
    "must be stopped (409 otherwise).",
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
    description="Rebuilds the network, resets the simulation, restarts the protocol interfaces "
    "the site enables (e.g. Modbus) and records the site as the one to load at startup. The "
    "engine stays stopped: POST /api/sim/start.",
)
async def activate_site(name: str, context: AdapterContext = Depends(get_context)) -> SiteConfig:
    return await context.library.activate(name)


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
    summary="One JSON Schema (site-config)",
)
async def get_schema(
    name: str, context: AdapterContext = Depends(get_context)
) -> dict[str, JsonValue]:
    return context.library.get_schema(name)
