"""OpenMeteoProvider: weather and plane-of-array irradiance from Open-Meteo's forecast API (NOAA
HRRR and other models, chosen by Open-Meteo per location). The only code that knows Open-Meteo's
URL, parameters, field names, units and conventions.

- Base URL is configurable: the hosted API (https://api.open-meteo.com), the commercial API
  (https://customer-api.open-meteo.com with an API key) or a self-hosted server.
- 15-minute data: `minutely_15`; hourly: `hourly`. Radiation is the mean over the PRECEDING step,
  so a value stamped t covers [t - step, t). Temperature and wind are instantaneous at t and are
  used as that interval's value.
- Azimuth: Open-Meteo uses 0 = south, -90 = east, 90 = west; ours is clockwise from north
  (180 = south), so open_meteo = ours - 180.
- Wind arrives in km/h and is converted to m/s.
- Cloud cover has no 15-minute series: the same request also asks for it hourly, and each
  15-minute interval takes the value of the hour it starts in.
- One request per distinct (tilt, azimuth) plane, for global_tilted_irradiance (POA).
- Retries (tenacity, exponential backoff) on transport errors, 429 and 5xx. Every failure is
  raised as ProviderError.
- The free API is for non-commercial use only; attribution: "Weather data by Open-Meteo.com"
  (CC BY 4.0).
"""

import asyncio
import math
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import SecretStr, ValidationError
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from intelli_gateway.schemas.open_meteo.responses import (
    OpenMeteoErrorResponse,
    OpenMeteoForecastResponse,
    OpenMeteoSeries,
)
from intelli_gateway.schemas.solar_forecast import (
    PvArrayConfig,
    SiteConfig,
    WeatherForecast,
    WeatherInterval,
    WeatherProviderCapabilities,
)
from intelli_gateway.utils.exceptions import ProviderError

NAME = "open_meteo"
HOSTED_FREE_HOST = "api.open-meteo.com"
SERIES_BY_RESOLUTION = {15: "minutely_15", 60: "hourly"}
BASE_VARIABLES = (
    "shortwave_radiation",
    "direct_normal_irradiance",
    "diffuse_radiation",
    "temperature_2m",
    "wind_speed_10m",
)
MAX_FORECAST_DAYS = 16
KMH_PER_MS = 3.6

Plane = tuple[float, float]  # (tilt_deg, azimuth_deg) in our convention


def to_open_meteo_azimuth(azimuth_deg: float) -> float:
    """Ours: clockwise from north, 180 = south. Open-Meteo: 0 = south, -90 = east, 90 = west."""
    converted = azimuth_deg - 180.0
    return converted + 360.0 if converted < -180.0 else converted


def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, httpx.TransportError):  # connect/read errors and timeouts
        return True
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        return status == 429 or status >= 500
    return False


class _RateLimiter:
    """At most `max_calls` requests in any 60 s window (the free tier allows 600/min)."""

    def __init__(self, max_calls: int, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._max_calls = max_calls
        self._monotonic = monotonic
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = self._monotonic()
                while self._calls and now - self._calls[0] >= 60.0:
                    self._calls.popleft()
                if len(self._calls) < self._max_calls:
                    self._calls.append(now)
                    return
                await asyncio.sleep(60.0 - (now - self._calls[0]))


class OpenMeteoProvider:
    def __init__(
        self,
        base_url: str,
        timeout_s: float,
        attempts: int,
        api_key: SecretStr | None = None,
        max_calls_per_minute: int = 500,
        transport: httpx.AsyncBaseTransport | None = None,
        max_wait_s: float = 4.0,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url, timeout=httpx.Timeout(timeout_s), transport=transport
        )
        self._api_key = api_key
        self._attempts = attempts
        self._max_wait_s = max_wait_s
        self._clock = clock
        self._limiter = _RateLimiter(max_calls_per_minute)

    @property
    def name(self) -> str:
        return NAME

    def capabilities(self) -> WeatherProviderCapabilities:
        free_hosted = HOSTED_FREE_HOST in self._base_url and self._api_key is None
        return WeatherProviderCapabilities(
            resolutions_minutes=tuple(SERIES_BY_RESOLUTION),
            max_horizon_hours=MAX_FORECAST_DAYS * 24,
            variables=(*BASE_VARIABLES, "global_tilted_irradiance"),
            provides_poa=True,
            # The free hosted API is non-commercial; a paid key or a self-hosted server is not.
            commercial_use_allowed=not free_hosted,
        )

    async def fetch_forecast(
        self, site: SiteConfig, horizon_hours: int, resolution_minutes: int
    ) -> WeatherForecast:
        series_key = SERIES_BY_RESOLUTION.get(resolution_minutes)
        if series_key is None:
            raise ProviderError(
                f"open_meteo supports {sorted(SERIES_BY_RESOLUTION)} minute resolutions, "
                f"not {resolution_minutes}"
            )
        if not 1 <= horizon_hours <= MAX_FORECAST_DAYS * 24:
            raise ProviderError(f"open_meteo horizon must be 1..{MAX_FORECAST_DAYS * 24} h")
        issued_at = self._clock()
        step = timedelta(minutes=resolution_minutes)
        planes = _planes(site.arrays)
        base_plane, *other_planes = planes
        responses = await asyncio.gather(
            self._request(site, series_key, horizon_hours, base_plane, base=True),
            *(
                self._request(site, series_key, horizon_hours, plane, base=False)
                for plane in other_planes
            ),
        )
        series_by_plane = [_series(response, series_key) for response in responses]
        gti_by_plane = {
            plane: _gti_by_end(series)
            for plane, series in zip(planes, series_by_plane, strict=True)
        }
        # Hourly cloud cover, sent along with a 15-minute base request (None for hourly data,
        # whose own series carries it).
        cloud_by_hour = _cloud_by_hour(responses[0]) if series_key == "minutely_15" else None
        horizon_end = issued_at + timedelta(hours=horizon_hours)
        intervals = _intervals(
            series_by_plane[0],
            step,
            site.arrays,
            gti_by_plane,
            issued_at,
            horizon_end,
            cloud_by_hour,
        )
        if not intervals:
            raise ProviderError("open_meteo returned no usable intervals for the horizon")
        return WeatherForecast(
            site_id=site.site_id,
            provider_name=NAME,
            issued_at=issued_at,
            resolution_minutes=resolution_minutes,
            intervals=tuple(intervals),
        )

    async def health_check(self) -> bool:
        try:
            await self._get(
                {
                    "latitude": 0,
                    "longitude": 0,
                    "hourly": "temperature_2m",
                    "forecast_hours": 1,
                    "timezone": "UTC",
                }
            )
        except ProviderError:
            return False
        return True

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- request / response ---

    async def _request(
        self, site: SiteConfig, series_key: str, horizon_hours: int, plane: Plane, base: bool
    ) -> OpenMeteoForecastResponse:
        tilt_deg, azimuth_deg = plane
        variables = (
            (*BASE_VARIABLES, "global_tilted_irradiance") if base else ("global_tilted_irradiance",)
        )
        if base and series_key == "hourly":
            variables = (*variables, "cloud_cover")
        params: dict[str, str | int | float] = {
            "latitude": site.location.latitude,
            "longitude": site.location.longitude,
            "timezone": "UTC",
            # Whole days from today 00:00 UTC; trimmed to [now, now + horizon] afterwards.
            "forecast_days": min(MAX_FORECAST_DAYS, math.ceil(horizon_hours / 24) + 1),
            "tilt": tilt_deg,
            "azimuth": to_open_meteo_azimuth(azimuth_deg),
            series_key: ",".join(variables),
        }
        if base and series_key == "minutely_15":
            params["hourly"] = "cloud_cover"
        if site.location.elevation_m is not None:
            params["elevation"] = site.location.elevation_m
        body = await self._get(params)
        try:
            return OpenMeteoForecastResponse.model_validate_json(body)
        except ValidationError as error:
            raise ProviderError("open_meteo returned an unexpected payload") from error

    async def _get(self, params: dict[str, str | int | float]) -> bytes:
        if self._api_key is not None:
            params = {**params, "apikey": self._api_key.get_secret_value()}
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._attempts),
                wait=wait_exponential(multiplier=0.5, max=self._max_wait_s),
                retry=retry_if_exception(_is_retryable),
                reraise=True,
            ):
                with attempt:
                    await self._limiter.acquire()
                    response = await self._client.get("/v1/forecast", params=params)
                    response.raise_for_status()
                    return response.content
        except httpx.HTTPStatusError as error:
            raise ProviderError(
                f"open_meteo returned {error.response.status_code}: {_reason(error.response)}"
            ) from error
        except httpx.HTTPError as error:
            raise ProviderError(f"open_meteo unreachable ({type(error).__name__})") from error
        raise ProviderError("open_meteo request failed")  # unreachable: reraise=True


def _reason(response: httpx.Response) -> str:
    try:
        return OpenMeteoErrorResponse.model_validate_json(response.content).reason
    except ValidationError:
        return "no reason given"


def _planes(arrays: tuple[PvArrayConfig, ...]) -> list[Plane]:
    planes: list[Plane] = []
    for array in arrays:
        plane = (array.tilt_deg, array.azimuth_deg)
        if plane not in planes:
            planes.append(plane)
    return planes


def _parse_time(stamp: str) -> datetime:
    """Open-Meteo sends local ISO times without offset; we always request timezone=UTC."""
    moment = datetime.fromisoformat(stamp)
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def _series(response: OpenMeteoForecastResponse, series_key: str) -> OpenMeteoSeries:
    series = response.minutely_15 if series_key == "minutely_15" else response.hourly
    if series is None:
        raise ProviderError(f"open_meteo response has no {series_key} block")
    return series


def _cloud_by_hour(response: OpenMeteoForecastResponse) -> dict[datetime, float]:
    """Hourly cloud cover by its hour (Open-Meteo stamps it at the hour)."""
    hourly = response.hourly
    if hourly is None or hourly.cloud_cover is None:
        return {}
    return {
        _parse_time(stamp): value
        for stamp, value in zip(hourly.time, hourly.cloud_cover, strict=False)
        if value is not None
    }


def _gti_by_end(series: OpenMeteoSeries) -> dict[datetime, float]:
    values = series.global_tilted_irradiance or []
    return {
        _parse_time(stamp): value
        for stamp, value in zip(series.time, values, strict=False)
        if value is not None
    }


def _at(values: list[float | None] | None, index: int) -> float | None:
    if values is None or index >= len(values):
        return None
    return values[index]


def _intervals(
    series: OpenMeteoSeries,
    step: timedelta,
    arrays: tuple[PvArrayConfig, ...],
    gti_by_plane: dict[Plane, dict[datetime, float]],
    issued_at: datetime,
    horizon_end: datetime,
    cloud_by_hour: dict[datetime, float] | None,
) -> list[WeatherInterval]:
    intervals: list[WeatherInterval] = []
    for index, stamp in enumerate(series.time):
        end = _parse_time(stamp)
        start = end - step
        if end <= issued_at or start >= horizon_end:
            continue
        ghi = _at(series.shortwave_radiation, index)
        dni = _at(series.direct_normal_irradiance, index)
        dhi = _at(series.diffuse_radiation, index)
        temp = _at(series.temperature_2m, index)
        wind_kmh = _at(series.wind_speed_10m, index)
        if ghi is None or dni is None or dhi is None or temp is None or wind_kmh is None:
            continue  # the model's run doesn't reach this far yet
        poa_by_array: dict[int, float] = {}
        for array in arrays:
            poa = gti_by_plane[(array.tilt_deg, array.azimuth_deg)].get(end)
            if poa is not None:
                poa_by_array[array.array_id] = max(poa, 0.0)
        intervals.append(
            WeatherInterval(
                interval_start=start,
                interval_end=end,
                ghi=max(ghi, 0.0),
                dni=max(dni, 0.0),
                dhi=max(dhi, 0.0),
                temp_air_c=temp,
                wind_speed_ms=max(wind_kmh, 0.0) / KMH_PER_MS,
                cloud_cover_pct=(
                    _at(series.cloud_cover, index)
                    if cloud_by_hour is None
                    else cloud_by_hour.get(start.replace(minute=0, second=0, microsecond=0))
                ),
                poa_by_array=poa_by_array,
            )
        )
    return intervals
