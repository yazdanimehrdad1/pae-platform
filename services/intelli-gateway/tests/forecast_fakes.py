"""Shared PV-forecast test data: a fake Open-Meteo server (httpx MockTransport) that answers like
the real /v1/forecast, and the site configs the tests forecast."""

import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx

from intelli_gateway.schemas.solar_forecast import ForecastLocation, PvArrayConfig, SiteConfig
from intelli_gateway.services.open_meteo.provider import OpenMeteoProvider

FORECAST_NOW = datetime(2026, 6, 15, 10, 7, tzinfo=UTC)

SITE = SiteConfig(
    site_id=1001,
    name="Test PV",
    timezone="America/Phoenix",
    location=ForecastLocation(latitude=33.45, longitude=-112.07, elevation_m=331.0),
    arrays=(
        PvArrayConfig(
            array_id=7,
            name="pv1",
            tilt_deg=25,
            azimuth_deg=180,
            dc_capacity_kw=6500,
            ac_capacity_kw=5000,
        ),
    ),
)
TWO_PLANE_SITE = SITE.model_copy(
    update={
        "arrays": (
            *SITE.arrays,
            PvArrayConfig(
                array_id=8,
                name="pv2",
                tilt_deg=10,
                azimuth_deg=90,
                dc_capacity_kw=1000,
                ac_capacity_kw=800,
            ),
        )
    }
)


def fixed_now() -> datetime:
    return FORECAST_NOW


def _irradiance(moment: datetime) -> float:
    """A daytime bump in W/m2, peaking at 19:00 UTC (local noon in Arizona)."""
    hours_from_noon = (moment.hour + moment.minute / 60) - 19.0
    return (
        max(0.0, 900.0 * math.cos(hours_from_noon / 7.0 * math.pi / 2))
        if abs(hours_from_noon) < 7
        else 0.0
    )


def open_meteo_payload(request: httpx.Request) -> dict[str, object]:
    """What Open-Meteo returns for this request: series from today 00:00 UTC, per the request's
    variables, step and forecast_days."""
    params = request.url.params
    series_key = "minutely_15" if "minutely_15" in params else "hourly"
    step = timedelta(minutes=15 if series_key == "minutely_15" else 60)
    variables = params[series_key].split(",")
    days = int(params.get("forecast_days", "1"))
    start = FORECAST_NOW.replace(hour=0, minute=0)
    times = [start + step * (index + 1) for index in range(int(days * timedelta(days=1) / step))]
    gti_scale = 1.1 if float(params.get("tilt", "0")) > 15 else 1.0
    columns: dict[str, list[float | None]] = {
        "shortwave_radiation": [_irradiance(time - step / 2) for time in times],
        "direct_normal_irradiance": [_irradiance(time - step / 2) * 0.8 for time in times],
        "diffuse_radiation": [_irradiance(time - step / 2) * 0.15 for time in times],
        "global_tilted_irradiance": [_irradiance(time - step / 2) * gti_scale for time in times],
        "temperature_2m": [30.0 for _ in times],
        "wind_speed_10m": [7.2 for _ in times],  # km/h = 2 m/s
        "cloud_cover": [10.0 for _ in times],
    }
    # The model run doesn't reach the end of the last day: Open-Meteo pads with nulls.
    for name in columns:
        columns[name][-4:] = [None] * 4
    block: dict[str, object] = {"time": [time.strftime("%Y-%m-%dT%H:%M") for time in times]}
    block.update({name: columns[name] for name in variables})
    return {
        "latitude": float(params["latitude"]),
        "longitude": float(params["longitude"]),
        "utc_offset_seconds": 0,
        series_key: block,
    }


def open_meteo_provider(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    attempts: int = 3,
    base_url: str = "https://api.open-meteo.com",
) -> OpenMeteoProvider:
    def default(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=open_meteo_payload(request))

    return OpenMeteoProvider(
        base_url=base_url,
        timeout_s=1.0,
        attempts=attempts,
        transport=httpx.MockTransport(handler or default),
        max_wait_s=0.0,
        clock=fixed_now,
    )


def failing_open_meteo(status: int | None = 503, body: bytes | None = None) -> OpenMeteoProvider:
    """A provider whose server always fails: an HTTP status, a bad body, or a timeout (None)."""

    def handle(request: httpx.Request) -> httpx.Response:
        if body is not None:
            return httpx.Response(200, content=body)
        if status is None:
            raise httpx.ConnectTimeout("slow", request=request)
        return httpx.Response(status, json={"error": True, "reason": "boom"})

    return open_meteo_provider(handle)
