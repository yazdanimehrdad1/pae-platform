"""Fakes for the PV forecast: fictional site configs, a clear-sky weather provider, a PV-power
source (the shape a Solcast-like API would have), and an in-memory repository. They prove the
facade, storage and API work with no real provider, and let `USE_FAKE_DATA=true` run offline."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pandas as pd
import pvlib

from intelli_gateway.schemas.solar_forecast import (
    FetchLogEntry,
    ForecastLocation,
    PvArrayConfig,
    PVForecast,
    PVInterval,
    SiteConfig,
    SourceCapabilities,
    SourceKind,
    WeatherForecast,
    WeatherInterval,
    WeatherProviderCapabilities,
)
from intelli_gateway.utils.exceptions import ProviderError

# Sunfield (fake site 1): its two inverters INV1 (10) and INV2 (11), 2.5 MW AC each.
# Windridge (fake site 2) is a wind farm: no PV arrays, so it is not forecast.
FAKE_SITE_CONFIGS: tuple[SiteConfig, ...] = (
    SiteConfig(
        site_id=1,
        name="Sunfield",
        timezone="Europe/Berlin",
        location=ForecastLocation(latitude=48.10, longitude=11.50, elevation_m=520.0),
        arrays=(
            PvArrayConfig(
                array_id=10,
                name="INV1",
                tilt_deg=25,
                azimuth_deg=180,
                dc_capacity_kw=3000,
                ac_capacity_kw=2500,
            ),
            PvArrayConfig(
                array_id=11,
                name="INV2",
                tilt_deg=25,
                azimuth_deg=180,
                dc_capacity_kw=3000,
                ac_capacity_kw=2500,
            ),
        ),
    ),
)


def _floor(moment: datetime, step: timedelta) -> datetime:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return epoch + ((moment - epoch) // step) * step


def _steps(issued_at: datetime, horizon_hours: int, resolution_minutes: int) -> list[datetime]:
    step = timedelta(minutes=resolution_minutes)
    first = _floor(issued_at, step)
    count = horizon_hours * 60 // resolution_minutes
    return [first + index * step for index in range(count)]


class FakeSiteConfigSource:
    def __init__(self, sites: tuple[SiteConfig, ...] = FAKE_SITE_CONFIGS) -> None:
        self._sites = {site.site_id: site for site in sites}

    async def list_sites(self) -> list[SiteConfig]:
        return list(self._sites.values())

    async def get_site(self, site_id: int) -> SiteConfig | None:
        return self._sites.get(site_id)


class FakeWeatherProvider:
    """Clear-sky irradiance (pvlib Ineichen) at the site, 20 degC, 2 m/s. No POA: the PV model
    transposes. `fail=True` makes every fetch raise ProviderError (for fallback tests)."""

    def __init__(
        self,
        name: str = "fake_weather",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        fail: bool = False,
    ) -> None:
        self._name = name
        self._clock = clock
        self.fail = fail
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    def capabilities(self) -> WeatherProviderCapabilities:
        return WeatherProviderCapabilities(
            resolutions_minutes=(15, 60),
            max_horizon_hours=384,
            variables=("ghi", "dni", "dhi", "temp_air_c", "wind_speed_ms"),
            provides_poa=False,
            commercial_use_allowed=True,
        )

    async def fetch_forecast(
        self, site: SiteConfig, horizon_hours: int, resolution_minutes: int
    ) -> WeatherForecast:
        self.calls += 1
        if self.fail:
            raise ProviderError(f"{self._name} is down (fake)")
        issued_at = self._clock()
        starts = _steps(issued_at, horizon_hours, resolution_minutes)
        step = timedelta(minutes=resolution_minutes)
        midpoints = pd.DatetimeIndex([start + step / 2 for start in starts])
        location = pvlib.location.Location(
            site.location.latitude,
            site.location.longitude,
            altitude=site.location.elevation_m or 0.0,
        )
        clearsky = location.get_clearsky(midpoints, model="ineichen")
        return WeatherForecast(
            site_id=site.site_id,
            provider_name=self._name,
            issued_at=issued_at,
            resolution_minutes=resolution_minutes,
            intervals=tuple(
                WeatherInterval(
                    interval_start=start,
                    interval_end=start + step,
                    ghi=max(float(clearsky["ghi"].iloc[index]), 0.0),
                    dni=max(float(clearsky["dni"].iloc[index]), 0.0),
                    dhi=max(float(clearsky["dhi"].iloc[index]), 0.0),
                    temp_air_c=20.0,
                    wind_speed_ms=2.0,
                )
                for index, start in enumerate(starts)
            ),
        )

    async def health_check(self) -> bool:
        return not self.fail

    async def aclose(self) -> None:
        return None


class FakePvPowerSource:
    """A PV-power prediction source: returns kW for the site directly (no weather, no per-array
    breakdown), as a Solcast- or Solargis-style API would. Fixed at half the AC capacity from
    08:00 to 16:00 UTC, so tests can predict every value."""

    def __init__(
        self,
        name: str = "fake_pv_power",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        fail: bool = False,
    ) -> None:
        self._name = name
        self._clock = clock
        self.fail = fail
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    def capabilities(self) -> SourceCapabilities:
        return SourceCapabilities(
            kind=SourceKind.PV_POWER,
            provides_weather=False,
            resolutions_minutes=(15, 30, 60),
            max_horizon_hours=168,
            commercial_use_allowed=True,
        )

    async def forecast(
        self, site: SiteConfig, horizon_hours: int, resolution_minutes: int
    ) -> PVForecast:
        self.calls += 1
        if self.fail:
            raise ProviderError(f"{self._name} is down (fake)")
        issued_at = self._clock()
        step = timedelta(minutes=resolution_minutes)
        intervals: list[PVInterval] = []
        for start in _steps(issued_at, horizon_hours, resolution_minutes):
            kw = site.ac_capacity_kw / 2 if 8 <= start.hour < 16 else 0.0
            intervals.append(
                PVInterval(
                    interval_start=start,
                    interval_end=start + step,
                    pv_ac_kw=kw,
                    pv_energy_kwh=kw * resolution_minutes / 60,
                )
            )
        return PVForecast(
            site_id=site.site_id,
            source_name=self._name,
            source_kind=SourceKind.PV_POWER,
            issued_at=issued_at,
            resolution_minutes=resolution_minutes,
            intervals=tuple(intervals),
        )

    async def health_check(self) -> bool:
        return not self.fail

    async def aclose(self) -> None:
        return None


class InMemoryForecastRepository:
    """Process-local storage with the same semantics as the Postgres repository."""

    def __init__(self) -> None:
        self.forecasts: list[PVForecast] = []
        self.fetch_log: list[FetchLogEntry] = []

    async def save(self, forecast: PVForecast) -> None:
        self.forecasts.append(forecast)

    async def latest(self, site_id: int) -> PVForecast | None:
        candidates = [
            (index, forecast)
            for index, forecast in enumerate(self.forecasts)
            if forecast.site_id == site_id
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: (item[1].issued_at, item[0]))[1]

    async def log_fetch(self, entry: FetchLogEntry) -> None:
        self.fetch_log.append(entry)

    async def last_fetch(self, site_id: int, ok: bool | None = None) -> FetchLogEntry | None:
        entries = [
            entry
            for entry in self.fetch_log
            if entry.site_id == site_id and (ok is None or entry.ok == ok)
        ]
        return entries[-1] if entries else None

    async def delete_issued_before(self, cutoff: datetime) -> int:
        before = len(self.forecasts)
        self.forecasts = [forecast for forecast in self.forecasts if forecast.issued_at >= cutoff]
        self.fetch_log = [entry for entry in self.fetch_log if entry.attempted_at >= cutoff]
        return before - len(self.forecasts)

    async def aclose(self) -> None:
        return None
