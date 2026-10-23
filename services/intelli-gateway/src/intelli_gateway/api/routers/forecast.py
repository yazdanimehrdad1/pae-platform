"""PV forecast endpoints. Thin: check access, call ForecastService, serialize. No provider,
pvlib or business logic here."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from intelli_gateway.api.dependencies import (
    get_forecast_service,
    get_request_context,
    require_role,
    require_site_access,
)
from intelli_gateway.schemas.api_models.forecast import (
    ForecastHealthResponse,
    PvForecastResponse,
    RefreshResponse,
)
from intelli_gateway.schemas.api_models.responses import ErrorResponse
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.solar_forecast.service import ForecastService

router = APIRouter(prefix="/v1", tags=["forecast"])

REFRESH_ROLE = "admin"


@router.get(
    "/forecast/health",
    response_model=ForecastHealthResponse,
    summary="PV forecast health: active provider, fallbacks, last success per site",
)
async def forecast_health(
    ctx: RequestContext = Depends(get_request_context),
    service: ForecastService = Depends(get_forecast_service),
) -> ForecastHealthResponse:
    health = await service.health()
    visible = tuple(site for site in health.sites if ctx.can_access_site(site.site_id))
    return ForecastHealthResponse.of(health.model_copy(update={"sites": visible}))


@router.post(
    "/forecast/refresh",
    response_model=RefreshResponse,
    summary="Fetch new PV forecasts now (admin)",
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def refresh_forecast(
    site_id: int | None = Query(None, description="One site; omit for every forecastable site"),
    ctx: RequestContext = Depends(get_request_context),
    service: ForecastService = Depends(get_forecast_service),
) -> RefreshResponse:
    require_role(ctx, REFRESH_ROLE)
    if site_id is not None:
        require_site_access(ctx, site_id)
    return RefreshResponse.of(await service.refresh(site_id))


@router.get(
    "/sites/{site_id}/forecast/series",
    response_model=PvForecastResponse,
    summary="The PV forecast over a window: AC power and weather (past: as forecast then)",
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse, "description": "No forecast stored for the window"},
        422: {"model": ErrorResponse},
    },
)
async def get_forecast_series(
    site_id: int,
    start: datetime = Query(..., description="ISO 8601 with offset"),
    end: datetime = Query(..., description="ISO 8601 with offset; may be in the future"),
    ctx: RequestContext = Depends(get_request_context),
    service: ForecastService = Depends(get_forecast_service),
) -> PvForecastResponse:
    """Each 15-minute interval comes from the newest forecast issued at or before its start, so
    past intervals show what was predicted just before them (compare with actual output) and
    future ones the latest forecast. For charting next to measurements."""
    require_site_access(ctx, site_id)
    return PvForecastResponse.of(await service.get_as_forecast(site_id, start, end))
