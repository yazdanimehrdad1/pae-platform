"""PV forecast endpoints. Thin: check access, call ForecastService, serialize. No provider,
pvlib or business logic here."""

import csv
import io
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from intelli_gateway.api.dependencies import (
    get_forecast_service,
    get_request_context,
    require_role,
    require_site_access,
)
from intelli_gateway.schemas.api_models.forecast import (
    DailySummaryResponse,
    ForecastHealthResponse,
    PvForecastResponse,
    RefreshResponse,
    WeatherForecastResponse,
)
from intelli_gateway.schemas.api_models.responses import ErrorResponse
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.solar_forecast import PVForecast
from intelli_gateway.solar_forecast.service import ForecastService

router = APIRouter(prefix="/v1", tags=["forecast"])

REFRESH_ROLE = "admin"
SITE_ERRORS: dict[int | str, dict[str, object]] = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse, "description": "No forecast stored for the site"},
    422: {"model": ErrorResponse},
}
CSV_COLUMNS = (
    "interval_start",
    "interval_end",
    "pv_ac_kw",
    "pv_energy_kwh",
    "pv_dc_kw",
    "ghi",
    "dni",
    "dhi",
    "temp_air_c",
    "wind_speed_ms",
    "cloud_cover_pct",
)

Resolution = Query(None, ge=1, description="Minutes; a multiple of the stored resolution")
OutputFormat = Literal["json", "csv"]


def _csv(forecast: PVForecast) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for interval in forecast.intervals:
        values = interval.model_dump()
        writer.writerow(
            [
                value.isoformat() if isinstance(value, datetime) else value
                for value in (values[column] for column in CSV_COLUMNS)
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"X-Forecast-Provider": forecast.source_name},
    )


def _respond(forecast: PVForecast, output: OutputFormat) -> PvForecastResponse | Response:
    return _csv(forecast) if output == "csv" else PvForecastResponse.of(forecast)


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
    "/sites/{site_id}/forecast",
    response_model=PvForecastResponse,
    summary="The latest PV forecast of a site over a window",
    responses={**SITE_ERRORS, 200: {"content": {"text/csv": {}}}},
)
async def get_forecast(
    site_id: int,
    start: datetime | None = Query(None, description="ISO 8601 with offset; omit = from the start"),
    end: datetime | None = Query(None, description="ISO 8601 with offset; omit = to the end"),
    resolution: int | None = Resolution,
    output: OutputFormat = Query("json", alias="format"),
    ctx: RequestContext = Depends(get_request_context),
    service: ForecastService = Depends(get_forecast_service),
) -> PvForecastResponse | Response:
    require_site_access(ctx, site_id)
    return _respond(await service.get_forecast(site_id, start, end, resolution), output)


@router.get(
    "/sites/{site_id}/forecast/latest",
    response_model=PvForecastResponse,
    summary="The latest PV forecast of a site, in full",
    responses=SITE_ERRORS,
)
async def get_latest_forecast(
    site_id: int,
    ctx: RequestContext = Depends(get_request_context),
    service: ForecastService = Depends(get_forecast_service),
) -> PvForecastResponse:
    require_site_access(ctx, site_id)
    return PvForecastResponse.of(await service.get_latest(site_id))


@router.get(
    "/sites/{site_id}/forecast/summary",
    response_model=DailySummaryResponse,
    summary="Forecast energy, peak and first/last production for one local day",
    responses=SITE_ERRORS,
)
async def get_forecast_summary(
    site_id: int,
    day: date = Query(..., alias="date", description="The site's local date, YYYY-MM-DD"),
    ctx: RequestContext = Depends(get_request_context),
    service: ForecastService = Depends(get_forecast_service),
) -> DailySummaryResponse:
    require_site_access(ctx, site_id)
    return DailySummaryResponse.of(await service.get_daily_summary(site_id, day))


@router.get(
    "/sites/{site_id}/forecast/history",
    response_model=PvForecastResponse,
    summary="What was forecast, as issued before a given time (backtesting)",
    responses={**SITE_ERRORS, 200: {"content": {"text/csv": {}}}},
)
async def get_forecast_history(
    site_id: int,
    issued_before: datetime = Query(..., description="ISO 8601 with offset"),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    resolution: int | None = Resolution,
    output: OutputFormat = Query("json", alias="format"),
    ctx: RequestContext = Depends(get_request_context),
    service: ForecastService = Depends(get_forecast_service),
) -> PvForecastResponse | Response:
    require_site_access(ctx, site_id)
    forecast = await service.get_history(site_id, issued_before, start, end, resolution)
    return _respond(forecast, output)


@router.get(
    "/sites/{site_id}/forecast/raw",
    response_model=WeatherForecastResponse,
    summary="The weather behind the latest PV forecast (404 for PV-power-only sources)",
    responses=SITE_ERRORS,
)
async def get_raw_weather(
    site_id: int,
    ctx: RequestContext = Depends(get_request_context),
    service: ForecastService = Depends(get_forecast_service),
) -> WeatherForecastResponse:
    require_site_access(ctx, site_id)
    return WeatherForecastResponse.of(await service.get_raw_weather(site_id))
