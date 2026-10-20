"""PV forecast shapes, provider-neutral: every forecast source (weather API + our PV model, or a
PV-power prediction API) produces these, so storage, the facade and the API never see a source's
own format.

Conventions (one set, converted inside each source):
- Times are timezone-aware and UTC. An interval is [interval_start, interval_end).
- Every value is the mean over its interval, except energy (kWh), which is the sum.
- Irradiance W/m2, temperature degC, wind m/s, power kW, energy kWh, cloud cover percent.
- Azimuth: degrees clockwise from north (180 = south, 90 = east, 270 = west). Tilt: degrees
  from horizontal (0 = flat).
"""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

UNITS: dict[str, str] = {
    "ghi": "W/m2",
    "dni": "W/m2",
    "dhi": "W/m2",
    "poa": "W/m2",
    "temp_air_c": "degC",
    "cell_temp_c": "degC",
    "wind_speed_ms": "m/s",
    "cloud_cover_pct": "%",
    "pv_dc_kw": "kW",
    "pv_ac_kw": "kW",
    "pv_energy_kwh": "kWh",
}
INTERVAL_CONVENTION = "mean over [interval_start, interval_end); energy summed; times UTC"


def _utc(moment: datetime) -> datetime:
    return moment.astimezone(UTC)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class SourceKind(StrEnum):
    WEATHER_MODEL = "weather_model"  # weather API + this service's PV model
    PV_POWER = "pv_power"  # an API that predicts PV power itself


# --- site configuration ----------------------------------------------------------------------


class ForecastLocation(_Frozen):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float | None = None


class PvArrayConfig(_Frozen):
    """One PV array (the array behind one PV or INVERTER device)."""

    array_id: int  # backend-ot device id
    name: str
    tilt_deg: float = Field(ge=0, le=90)
    azimuth_deg: float = Field(ge=0, lt=360)  # clockwise from north, 180 = south
    dc_capacity_kw: float = Field(gt=0)
    ac_capacity_kw: float = Field(gt=0)
    system_loss_pct: float = Field(default=14.0, ge=0, lt=100)
    temp_coefficient_pct_per_c: float = Field(default=-0.35, ge=-2, le=0)


class SiteConfig(_Frozen):
    """A site the forecast covers: where it is and its PV arrays (at least one)."""

    site_id: int
    name: str
    timezone: str = "UTC"
    location: ForecastLocation
    arrays: tuple[PvArrayConfig, ...] = Field(min_length=1)

    @property
    def ac_capacity_kw(self) -> float:
        return sum(array.ac_capacity_kw for array in self.arrays)


# --- weather ---------------------------------------------------------------------------------


class _Interval(_Frozen):
    interval_start: AwareDatetime
    interval_end: AwareDatetime

    _to_utc = field_validator("interval_start", "interval_end")(_utc)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.interval_end <= self.interval_start:
            raise ValueError("interval_end must be after interval_start")
        return self


class WeatherInterval(_Interval):
    ghi: float = Field(ge=0)
    dni: float = Field(ge=0)
    dhi: float = Field(ge=0)
    temp_air_c: float
    wind_speed_ms: float = Field(ge=0)
    cloud_cover_pct: float | None = Field(default=None, ge=0, le=100)
    # Plane-of-array irradiance per array id, when the provider computes it; else the PV model does.
    poa_by_array: dict[int, float] = Field(default_factory=dict[int, float])


class WeatherForecast(_Frozen):
    site_id: int
    provider_name: str
    issued_at: AwareDatetime
    resolution_minutes: int = Field(gt=0)
    intervals: tuple[WeatherInterval, ...]

    _to_utc = field_validator("issued_at")(_utc)


class WeatherProviderCapabilities(_Frozen):
    resolutions_minutes: tuple[int, ...]
    max_horizon_hours: int
    variables: tuple[str, ...]
    provides_poa: bool
    commercial_use_allowed: bool


# --- PV forecast -----------------------------------------------------------------------------


class PVArrayInterval(_Frozen):
    array_id: int
    poa: float | None = None
    cell_temp_c: float | None = None
    pv_dc_kw: float | None = None
    pv_ac_kw: float = Field(ge=0)
    pv_energy_kwh: float = Field(ge=0)


class PVInterval(_Interval):
    """Site totals for one interval. Weather fields are None when the source has no weather."""

    ghi: float | None = None
    dni: float | None = None
    dhi: float | None = None
    temp_air_c: float | None = None
    wind_speed_ms: float | None = None
    cloud_cover_pct: float | None = None
    pv_dc_kw: float | None = None
    pv_ac_kw: float = Field(ge=0)
    pv_energy_kwh: float = Field(ge=0)
    # Per-array breakdown; empty when the source only predicts the site total.
    arrays: tuple[PVArrayInterval, ...] = ()


class PVForecast(_Frozen):
    site_id: int
    source_name: str
    source_kind: SourceKind
    issued_at: AwareDatetime
    resolution_minutes: int = Field(gt=0)
    intervals: tuple[PVInterval, ...]
    # Set by the facade: a fallback source produced this forecast (the primary failed).
    fallback_used: bool = False

    _to_utc = field_validator("issued_at")(_utc)


class SourceCapabilities(_Frozen):
    kind: SourceKind
    provides_weather: bool
    resolutions_minutes: tuple[int, ...]
    max_horizon_hours: int
    commercial_use_allowed: bool


# --- results of the facade -------------------------------------------------------------------


class DailySummary(_Frozen):
    site_id: int
    date: date  # the site's local date
    timezone: str
    source_name: str
    issued_at: AwareDatetime
    energy_kwh: float
    peak_kw: float
    peak_at: AwareDatetime | None  # start of the interval with the peak; None if no production
    first_production_at: AwareDatetime | None
    last_production_at: AwareDatetime | None
    # False when the stored forecast covers only part of the day.
    complete: bool


class FetchLogEntry(_Frozen):
    site_id: int
    source_name: str
    attempted_at: AwareDatetime
    ok: bool
    fallback_used: bool = False
    error: str | None = None


class SiteForecastHealth(_Frozen):
    site_id: int
    last_attempt_at: AwareDatetime | None
    last_success_at: AwareDatetime | None
    last_source: str | None
    fallback_in_use: bool
    last_error: str | None
    # No successful refresh for longer than twice the refresh interval.
    stale: bool


class ForecastHealth(_Frozen):
    enabled: bool
    active_source: str
    fallback_sources: tuple[str, ...]
    sites: tuple[SiteForecastHealth, ...]


class SiteRefreshResult(_Frozen):
    site_id: int
    ok: bool
    source_name: str | None = None
    fallback_used: bool = False
    intervals: int = 0
    error: str | None = None


class RefreshResult(_Frozen):
    started_at: AwareDatetime
    finished_at: AwareDatetime
    sites: tuple[SiteRefreshResult, ...]
