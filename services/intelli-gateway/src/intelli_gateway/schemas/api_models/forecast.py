"""PV forecast response bodies (the published contract): AC power and the weather. The
`provider` field names the source that produced the forecast."""

from datetime import datetime

from pydantic import BaseModel, Field

from intelli_gateway.schemas.solar_forecast import (
    INTERVAL_CONVENTION,
    UNITS,
    ForecastHealth,
    PVForecast,
    RefreshResult,
)


class ArrayIntervalResponse(BaseModel):
    array_id: int = Field(description="backend-ot device id of the PV array")
    pv_ac_kw: float


class ForecastIntervalResponse(BaseModel):
    interval_start: datetime
    interval_end: datetime
    pv_ac_kw: float = Field(description="Site AC power: the sum of its arrays")
    ghi: float | None = Field(description="Global horizontal irradiance")
    temp_air_c: float | None
    wind_speed_ms: float | None
    cloud_cover_pct: float | None
    arrays: list[ArrayIntervalResponse] = Field(
        description="AC power per PV device; empty when the source predicts the site total only"
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
                    ghi=interval.ghi,
                    temp_air_c=interval.temp_air_c,
                    wind_speed_ms=interval.wind_speed_ms,
                    cloud_cover_pct=interval.cloud_cover_pct,
                    arrays=[
                        ArrayIntervalResponse(array_id=array.array_id, pv_ac_kw=array.pv_ac_kw)
                        for array in interval.arrays
                    ],
                )
                for interval in forecast.intervals
            ],
        )


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
