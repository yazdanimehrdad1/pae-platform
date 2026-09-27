"""Assets, setpoints and points: /assets/*, /points."""

from fastapi import APIRouter, Depends

from powerflow.core.setpoints import BessSetpointRequest, PvSetpointRequest, SetpointResult
from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.interfaces.http.schemas import (
    AssetsResponse,
    BessAssetResponse,
    ErrorResponse,
    LoadAssetResponse,
    OpenApiResponses,
    PointsResponse,
    PointValueResponse,
    PvAssetResponse,
)
from powerflow.points import POINT_LISTS

router = APIRouter(tags=["assets"])
NOT_FOUND: OpenApiResponses = {
    404: {"model": ErrorResponse, "description": "Unknown asset or point."}
}
SETPOINT_DESCRIPTION = (
    "Partial update: omitted fields keep their value. Invalid values → 422; out-of-range values "
    "are clamped to the static limits (P ratings, S circle) and reported in `flags`. SOC and "
    "ramp limits apply every step and show up in the measurements' `limit_flags`."
)


@router.get("/assets", response_model=AssetsResponse, summary="All assets, static parameters")
async def list_assets(context: AdapterContext = Depends(get_context)) -> AssetsResponse:
    config = context.engine.config
    return AssetsResponse(bess=config.bess, pv=config.pv, loads=config.loads)


@router.get("/assets/bess/{asset_id}", response_model=BessAssetResponse, responses=NOT_FOUND)
async def get_bess(
    asset_id: str, context: AdapterContext = Depends(get_context)
) -> BessAssetResponse:
    asset = context.engine.runtime.bess_asset(asset_id)
    latest = context.engine.store.latest
    measurement = (
        next((item for item in latest.bess if item.id == asset_id), None) if latest else None
    )
    return BessAssetResponse(
        config=asset.config, setpoint=context.setpoints.bess(asset_id), measurement=measurement
    )


@router.put(
    "/assets/bess/{asset_id}/setpoint",
    response_model=SetpointResult,
    responses=NOT_FOUND,
    summary="Set a BESS's P/Q/mode (+P discharge, −P charge)",
    description=SETPOINT_DESCRIPTION,
)
async def put_bess_setpoint(
    asset_id: str, request: BessSetpointRequest, context: AdapterContext = Depends(get_context)
) -> SetpointResult:
    return context.setpoints.write_bess(asset_id, request)


@router.get("/assets/pv/{asset_id}", response_model=PvAssetResponse, responses=NOT_FOUND)
async def get_pv(asset_id: str, context: AdapterContext = Depends(get_context)) -> PvAssetResponse:
    asset = context.engine.runtime.pv_asset(asset_id)
    latest = context.engine.store.latest
    measurement = (
        next((item for item in latest.pv if item.id == asset_id), None) if latest else None
    )
    return PvAssetResponse(
        config=asset.config, setpoint=context.setpoints.pv(asset_id), measurement=measurement
    )


@router.put(
    "/assets/pv/{asset_id}/setpoint",
    response_model=SetpointResult,
    responses=NOT_FOUND,
    summary="Set a PV's curtailment (kW or %) and Q or power factor",
    description=SETPOINT_DESCRIPTION,
)
async def put_pv_setpoint(
    asset_id: str, request: PvSetpointRequest, context: AdapterContext = Depends(get_context)
) -> SetpointResult:
    return context.setpoints.write_pv(asset_id, request)


@router.get("/assets/load/{asset_id}", response_model=LoadAssetResponse, responses=NOT_FOUND)
async def get_load(
    asset_id: str, context: AdapterContext = Depends(get_context)
) -> LoadAssetResponse:
    asset = context.engine.runtime.load_asset(asset_id)
    latest = context.engine.store.latest
    measurement = (
        next((item for item in latest.loads if item.id == asset_id), None) if latest else None
    )
    return LoadAssetResponse(config=asset.config, measurement=measurement)


@router.get("/points", response_model=PointsResponse, summary="Protocol-neutral point lists")
async def list_points(context: AdapterContext = Depends(get_context)) -> PointsResponse:
    return PointsResponse(
        point_lists={str(asset_type): list(points) for asset_type, points in POINT_LISTS.items()},
        names=context.points.names(),
    )


@router.get(
    "/points/{name}",
    response_model=PointValueResponse,
    responses=NOT_FOUND,
    summary="Read one point by name, e.g. bess.bess1.soc_pct",
)
async def read_point(
    name: str, context: AdapterContext = Depends(get_context)
) -> PointValueResponse:
    _, definition = context.points.resolve(name)
    return PointValueResponse(name=name, value=context.points.read(name), unit=definition.unit)
