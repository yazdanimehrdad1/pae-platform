"""PV forecast response bodies (the published contract). Built from the facade's models; the
`provider` field names the source that produced the forecast."""

from datetime import date as LocalDate
from datetime import datetime

from pydantic import BaseModel, Field

from intelli_gateway.schemas.solar_forecast import (
    INTERVAL_CONVENTION,
    UNITS,
    DailySummary,
    ForecastHealth,
    PVForecast,
    RefreshResult,
    WeatherForecast,
)


class ArrayIntervalResponse(BaseModel):
    array_id: int = Field(description="backend-ot device id of the PV array")
    poa: float | None
    cell_temp_c: float | None
    pv_dc_kw: float | None
    pv_ac_kw: float
    pv_energy_kwh: float


class ForecastIntervalResponse(BaseModel):
    interval_start: datetime
    interval_end: datetime
    pv_ac_kw: float
    pv_energy_kwh: float
    pv_dc_kw: float | None
    ghi: float | None
    dni: float | None
    dhi: float | None
    temp_air_c: float | None
    wind_speed_ms: float | None
    cloud_cover_pct: float | None
    arrays: list[ArrayIntervalResponse] = Field(
        description="Per-array breakdown; empty when the source predicts the site total only"
    )


class PvForecastResponse(BaseModel):
    site_id: int
    provider: str = Field(description="The source that produced this forecast")
    source_kind: str = Field(description="weather_model (weather + PV model) or pv_power")
    fallback_used: bool = Field(description="A fallback produced it: the primary source failed")
    issued_at: datetime
    resolution_minutes: int
    interval_convention: str = INTERVAL_CONVENTION
    units: dict[str, str] = Field(default_factory=lambda: dict(UNITS))
    intervals: list[ForecastIntervalResponse]

    @classmethod
    def of(cls, forecast: PVForecast) -> "PvForecastResponse":
        return cls(
            site_id=forecast.site_id,
            provider=forecast.source_name,
            source_kind=forecast.source_kind.value,
            fallback_used=forecast.fallback_used,
            issued_at=forecast.issued_at,
            resolution_minutes=forecast.resolution_minutes,
            intervals=[
                ForecastIntervalResponse(
                    interval_start=interval.interval_start,
                    interval_end=interval.interval_end,
                    pv_ac_kw=interval.pv_ac_kw,
                    pv_energy_kwh=interval.pv_energy_kwh,
                    pv_dc_kw=interval.pv_dc_kw,
                    ghi=interval.ghi,
                    dni=interval.dni,
                    dhi=interval.dhi,
                    temp_air_c=interval.temp_air_c,
                    wind_speed_ms=interval.wind_speed_ms,
                    cloud_cover_pct=interval.cloud_cover_pct,
                    arrays=[
                        ArrayIntervalResponse(**array.model_dump()) for array in interval.arrays
                    ],
                )
                for interval in forecast.intervals
            ],
        )


class WeatherIntervalResponse(BaseModel):
    interval_start: datetime
    interval_end: datetime
    ghi: float
    dni: float
    dhi: float
    temp_air_c: float
    wind_speed_ms: float
    cloud_cover_pct: float | None
    poa_by_array: dict[str, float] = Field(description="Plane-of-array irradiance per array id")


class WeatherForecastResponse(BaseModel):
    site_id: int
    provider: str
    issued_at: datetime
    resolution_minutes: int
    interval_convention: str = INTERVAL_CONVENTION
    units: dict[str, str] = Field(default_factory=lambda: dict(UNITS))
    intervals: list[WeatherIntervalResponse]

    @classmethod
    def of(cls, weather: WeatherForecast) -> "WeatherForecastResponse":
        return cls(
            site_id=weather.site_id,
            provider=weather.provider_name,
            issued_at=weather.issued_at,
            resolution_minutes=weather.resolution_minutes,
            intervals=[
                WeatherIntervalResponse(
                    interval_start=interval.interval_start,
                    interval_end=interval.interval_end,
                    ghi=interval.ghi,
                    dni=interval.dni,
                    dhi=interval.dhi,
                    temp_air_c=interval.temp_air_c,
                    wind_speed_ms=interval.wind_speed_ms,
                    cloud_cover_pct=interval.cloud_cover_pct,
                    poa_by_array={str(key): value for key, value in interval.poa_by_array.items()},
                )
                for interval in weather.intervals
            ],
        )


class DailySummaryResponse(BaseModel):
    site_id: int
    date: LocalDate = Field(description="The site's local date")
    timezone: str
    provider: str
    issued_at: datetime
    energy_kwh: float
    peak_kw: float
    peak_at: datetime | None
    first_production_at: datetime | None
    last_production_at: datetime | None
    complete: bool = Field(description="False when the forecast covers only part of the day")

    @classmethod
    def of(cls, summary: DailySummary) -> "DailySummaryResponse":
        values = summary.model_dump()
        values["provider"] = values.pop("source_name")
        return cls(**values)


class SiteForecastHealthResponse(BaseModel):
    site_id: int
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_provider: str | None
    fallback_in_use: bool
    last_error: str | None
    stale: bool


class ForecastHealthResponse(BaseModel):
    enabled: bool
    active_provider: str
    fallback_providers: list[str]
    sites: list[SiteForecastHealthResponse]

    @classmethod
    def of(cls, health: ForecastHealth) -> "ForecastHealthResponse":
        return cls(
            enabled=health.enabled,
            active_provider=health.active_source,
            fallback_providers=list(health.fallback_sources),
            sites=[
                SiteForecastHealthResponse(
                    site_id=site.site_id,
                    last_attempt_at=site.last_attempt_at,
                    last_success_at=site.last_success_at,
                    last_provider=site.last_source,
                    fallback_in_use=site.fallback_in_use,
                    last_error=site.last_error,
                    stale=site.stale,
                )
                for site in health.sites
            ],
        )


class SiteRefreshResponse(BaseModel):
    site_id: int
    ok: bool
    provider: str | None
    fallback_used: bool
    intervals: int
    error: str | None


class RefreshResponse(BaseModel):
    started_at: datetime
    finished_at: datetime
    sites: list[SiteRefreshResponse]

    @classmethod
    def of(cls, result: RefreshResult) -> "RefreshResponse":
        return cls(
            started_at=result.started_at,
            finished_at=result.finished_at,
            sites=[
                SiteRefreshResponse(
                    site_id=site.site_id,
                    ok=site.ok,
                    provider=site.source_name,
                    fallback_used=site.fallback_used,
                    intervals=site.intervals,
                    error=site.error,
                )
                for site in result.sites
            ],
        )
