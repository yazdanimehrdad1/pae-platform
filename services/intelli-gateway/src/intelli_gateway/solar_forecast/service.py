"""ForecastService: the PV forecast facade, and the only thing API routers and tools call.

It depends on Protocols only: a SiteConfigSource (where sites are and their arrays), an ordered
list of PvForecastSources (primary first, then fallbacks) and a ForecastRepository. It never
sees a provider's format, pvlib or HTTP. Swapping a source changes the list it is given, not this.
"""

import logging
import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from intelli_gateway.interfaces.forecast_repository import ForecastRepository
from intelli_gateway.interfaces.pv_forecast_source import PvForecastSource
from intelli_gateway.interfaces.site_config_source import SiteConfigSource
from intelli_gateway.schemas.solar_forecast import (
    DailySummary,
    FetchLogEntry,
    ForecastHealth,
    PVArrayInterval,
    PVForecast,
    PVInterval,
    RefreshResult,
    SiteConfig,
    SiteForecastHealth,
    SiteRefreshResult,
    SourceCapabilities,
    SourceKind,
    WeatherForecast,
    WeatherInterval,
)
from intelli_gateway.utils.exceptions import (
    ConfigurationError,
    InvalidRequestError,
    NotFoundError,
    ProviderError,
    UpstreamUnavailableError,
)

logger = logging.getLogger(__name__)

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class ForecastSettings:
    enabled: bool
    horizon_hours: int
    resolution_minutes: int
    refresh_interval_minutes: int
    retention_days: int


class ForecastService:
    def __init__(
        self,
        sites: SiteConfigSource,
        sources: Sequence[PvForecastSource],
        repository: ForecastRepository,
        settings: ForecastSettings,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not sources:
            raise ConfigurationError("the PV forecast needs at least one source")
        self._sites = sites
        self._sources = list(sources)
        self._repository = repository
        self._settings = settings
        self._clock = clock
        self._known_site_ids: set[int] = set()

    @property
    def source_names(self) -> list[str]:
        return [source.name for source in self._sources]

    def source_capabilities(self) -> SourceCapabilities:
        """Capabilities of the primary source."""
        return self._sources[0].capabilities()

    # --- refresh ---------------------------------------------------------------------------

    async def refresh(self, site_id: int | None = None) -> RefreshResult:
        """Fetch a new forecast for one site or every forecastable site: the primary source
        first, then each fallback in order. Every attempt goes to the fetch log; each success is
        stored as a new run (history is kept). Then forecasts past retention are dropped."""
        if not self._settings.enabled:
            raise ConfigurationError("the PV forecast is disabled (FORECAST_ENABLED=false)")
        started_at = self._clock()
        if site_id is None:
            sites = await self._sites.list_sites()
        else:
            site = await self._sites.get_site(site_id)
            if site is None:
                raise NotFoundError(
                    f"site {site_id} can't be forecast (unknown, no coordinates or no PV array)"
                )
            sites = [site]
        results = [await self._refresh_site(site) for site in sites]
        cutoff = self._clock() - timedelta(days=self._settings.retention_days)
        dropped = await self._repository.delete_issued_before(cutoff)
        if dropped:
            logger.info("forecast_retention", extra={"fields": {"runs_deleted": dropped}})
        return RefreshResult(started_at=started_at, finished_at=self._clock(), sites=tuple(results))

    async def _refresh_site(self, site: SiteConfig) -> SiteRefreshResult:
        self._known_site_ids.add(site.site_id)
        errors: list[str] = []
        for index, source in enumerate(self._sources):
            fallback_used = index > 0
            attempted_at = self._clock()
            try:
                forecast = await source.forecast(
                    site, self._settings.horizon_hours, self._settings.resolution_minutes
                )
                if not forecast.intervals:
                    raise ProviderError(f"{source.name} returned no intervals")
                if forecast.site_id != site.site_id:
                    raise ProviderError(f"{source.name} returned a forecast for another site")
            except ProviderError as error:
                message = str(error)
            except Exception as error:  # a source bug must not stop the other sources or sites
                logger.exception(
                    "forecast_source_crashed",
                    extra={"fields": {"site_id": site.site_id, "source": source.name}},
                )
                message = f"{source.name} failed unexpectedly ({type(error).__name__})"
            else:
                forecast = forecast.model_copy(update={"fallback_used": fallback_used})
                await self._repository.save(forecast)
                await self._repository.log_fetch(
                    FetchLogEntry(
                        site_id=site.site_id,
                        source_name=source.name,
                        attempted_at=attempted_at,
                        ok=True,
                        fallback_used=fallback_used,
                    )
                )
                if fallback_used:
                    logger.warning(
                        "forecast_fallback_used",
                        extra={
                            "fields": {
                                "site_id": site.site_id,
                                "source": source.name,
                                "primary_errors": errors,
                            }
                        },
                    )
                logger.info(
                    "forecast_refreshed",
                    extra={
                        "fields": {
                            "site_id": site.site_id,
                            "source": source.name,
                            "intervals": len(forecast.intervals),
                        }
                    },
                )
                return SiteRefreshResult(
                    site_id=site.site_id,
                    ok=True,
                    source_name=source.name,
                    fallback_used=fallback_used,
                    intervals=len(forecast.intervals),
                )
            errors.append(message)
            await self._repository.log_fetch(
                FetchLogEntry(
                    site_id=site.site_id,
                    source_name=source.name,
                    attempted_at=attempted_at,
                    ok=False,
                    fallback_used=fallback_used,
                    error=message,
                )
            )
            logger.warning(
                "forecast_source_failed",
                extra={
                    "fields": {"site_id": site.site_id, "source": source.name, "error": message}
                },
            )
        return SiteRefreshResult(site_id=site.site_id, ok=False, error="; ".join(errors))

    # --- reads -----------------------------------------------------------------------------

    async def get_latest(self, site_id: int) -> PVForecast:
        return await self._stored(site_id)

    async def get_forecast(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution_minutes: int | None = None,
    ) -> PVForecast:
        """The latest forecast's intervals overlapping [start, end) (open ends: the whole
        forecast), resampled to resolution_minutes: kW and W/m2 are averaged, kWh summed."""
        _check_window(start, end)
        return _window(await self._stored(site_id), start, end, resolution_minutes)

    async def get_history(
        self,
        site_id: int,
        issued_before: datetime,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution_minutes: int | None = None,
    ) -> PVForecast:
        """What was forecast for [start, end) by the newest run issued before `issued_before`."""
        _check_window(start, end)
        if issued_before.tzinfo is None:
            raise InvalidRequestError("issued_before must carry a timezone offset")
        forecast = await self._repository.latest(site_id, issued_before=issued_before)
        if forecast is None:
            raise NotFoundError(f"no forecast for site {site_id} issued before {issued_before}")
        return _window(forecast, start, end, resolution_minutes)

    async def get_daily_summary(self, site_id: int, day: date) -> DailySummary:
        """Energy, peak and first/last production for one local day of the site."""
        forecast = await self._stored(site_id)
        site = await self._sites.get_site(site_id)
        timezone = site.timezone if site is not None else "UTC"
        try:
            zone = ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            zone, timezone = ZoneInfo("UTC"), "UTC"
        day_start = datetime.combine(day, time(), tzinfo=zone).astimezone(UTC)
        day_end = datetime.combine(day + timedelta(days=1), time(), tzinfo=zone).astimezone(UTC)
        inside = [
            interval
            for interval in forecast.intervals
            if interval.interval_start >= day_start and interval.interval_end <= day_end
        ]
        producing = [interval for interval in inside if interval.pv_ac_kw > 0]
        peak = max(inside, key=lambda interval: interval.pv_ac_kw, default=None)
        covered = sum(
            ((interval.interval_end - interval.interval_start) for interval in inside),
            timedelta(),
        )
        return DailySummary(
            site_id=site_id,
            date=day,
            timezone=timezone,
            source_name=forecast.source_name,
            issued_at=forecast.issued_at,
            energy_kwh=sum(interval.pv_energy_kwh for interval in inside),
            peak_kw=peak.pv_ac_kw if peak is not None else 0.0,
            peak_at=peak.interval_start if peak is not None and peak.pv_ac_kw > 0 else None,
            first_production_at=producing[0].interval_start if producing else None,
            last_production_at=producing[-1].interval_end if producing else None,
            complete=covered >= day_end - day_start,
        )

    async def get_raw_weather(self, site_id: int) -> WeatherForecast:
        """The weather behind the latest forecast. 404 when its source predicts PV power only."""
        forecast = await self._stored(site_id)
        if forecast.source_kind is SourceKind.PV_POWER or any(
            _missing_weather(interval) for interval in forecast.intervals
        ):
            raise NotFoundError(
                f"the latest forecast of site {site_id} comes from {forecast.source_name}, "
                "which provides no weather data"
            )
        return WeatherForecast(
            site_id=forecast.site_id,
            provider_name=forecast.source_name,
            issued_at=forecast.issued_at,
            resolution_minutes=forecast.resolution_minutes,
            intervals=tuple(
                WeatherInterval(
                    interval_start=interval.interval_start,
                    interval_end=interval.interval_end,
                    ghi=interval.ghi or 0.0,
                    dni=interval.dni or 0.0,
                    dhi=interval.dhi or 0.0,
                    temp_air_c=interval.temp_air_c or 0.0,
                    wind_speed_ms=interval.wind_speed_ms or 0.0,
                    cloud_cover_pct=interval.cloud_cover_pct,
                    poa_by_array={
                        array.array_id: array.poa
                        for array in interval.arrays
                        if array.poa is not None
                    },
                )
                for interval in forecast.intervals
            ),
        )

    async def list_sites(self) -> list[SiteConfig]:
        sites = await self._sites.list_sites()
        self._known_site_ids.update(site.site_id for site in sites)
        return sites

    async def health(self) -> ForecastHealth:
        """Last attempt and last success per site. If the site list can't be read (backend-ot
        down), the sites seen before are reported."""
        try:
            site_ids = sorted({site.site_id for site in await self.list_sites()})
        except UpstreamUnavailableError:
            site_ids = sorted(self._known_site_ids)
        now = self._clock()
        stale_after = timedelta(minutes=2 * max(self._settings.refresh_interval_minutes, 15))
        sites: list[SiteForecastHealth] = []
        for site_id in site_ids:
            last = await self._repository.last_fetch(site_id)
            success = await self._repository.last_fetch(site_id, ok=True)
            sites.append(
                SiteForecastHealth(
                    site_id=site_id,
                    last_attempt_at=last.attempted_at if last is not None else None,
                    last_success_at=success.attempted_at if success is not None else None,
                    last_source=success.source_name if success is not None else None,
                    fallback_in_use=success.fallback_used if success is not None else False,
                    last_error=last.error if last is not None and not last.ok else None,
                    stale=success is None or now - success.attempted_at > stale_after,
                )
            )
        return ForecastHealth(
            enabled=self._settings.enabled,
            active_source=self._sources[0].name,
            fallback_sources=tuple(source.name for source in self._sources[1:]),
            sites=tuple(sites),
        )

    async def aclose(self) -> None:
        for source in self._sources:
            await source.aclose()
        await self._repository.aclose()

    async def _stored(self, site_id: int) -> PVForecast:
        forecast = await self._repository.latest(site_id)
        if forecast is None:
            raise NotFoundError(f"no forecast stored for site {site_id} yet")
        return forecast


# --- pure helpers -------------------------------------------------------------------------


def _missing_weather(interval: PVInterval) -> bool:
    return any(
        value is None
        for value in (
            interval.ghi,
            interval.dni,
            interval.dhi,
            interval.temp_air_c,
            interval.wind_speed_ms,
        )
    )


def _check_window(start: datetime | None, end: datetime | None) -> None:
    if (start is not None and start.tzinfo is None) or (end is not None and end.tzinfo is None):
        raise InvalidRequestError("start and end must carry a timezone offset")
    if start is not None and end is not None and end <= start:
        raise InvalidRequestError("end must be after start")


def _window(
    forecast: PVForecast,
    start: datetime | None,
    end: datetime | None,
    resolution_minutes: int | None,
) -> PVForecast:
    inside = tuple(
        interval
        for interval in forecast.intervals
        if (start is None or interval.interval_end > start)
        and (end is None or interval.interval_start < end)
    )
    windowed = forecast.model_copy(update={"intervals": inside})
    return resample(windowed, resolution_minutes or forecast.resolution_minutes)


def _mean(values: Sequence[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None


def resample(forecast: PVForecast, resolution_minutes: int) -> PVForecast:
    """Coarser intervals, aligned to the UTC clock: means for kW, W/m2, degC and m/s; sums for
    kWh. The target must be a whole multiple of the stored resolution. A bucket at the edge of
    the forecast covers only the intervals it has (its kWh is not scaled up)."""
    stored = forecast.resolution_minutes
    if resolution_minutes == stored:
        return forecast
    if resolution_minutes < stored or resolution_minutes % stored:
        raise InvalidRequestError(
            f"resolution must be a whole multiple of the stored {stored} minutes"
        )
    step = timedelta(minutes=resolution_minutes)
    buckets: defaultdict[datetime, list[PVInterval]] = defaultdict(list)
    for interval in forecast.intervals:
        index = math.floor((interval.interval_start - EPOCH) / step)
        buckets[EPOCH + index * step].append(interval)
    intervals: list[PVInterval] = []
    for bucket_start in sorted(buckets):
        members = buckets[bucket_start]
        arrays_by_id: defaultdict[int, list[PVArrayInterval]] = defaultdict(list)
        for member in members:
            for array in member.arrays:
                arrays_by_id[array.array_id].append(array)
        intervals.append(
            PVInterval(
                interval_start=bucket_start,
                interval_end=bucket_start + step,
                ghi=_mean([member.ghi for member in members]),
                dni=_mean([member.dni for member in members]),
                dhi=_mean([member.dhi for member in members]),
                temp_air_c=_mean([member.temp_air_c for member in members]),
                wind_speed_ms=_mean([member.wind_speed_ms for member in members]),
                cloud_cover_pct=_mean([member.cloud_cover_pct for member in members]),
                pv_dc_kw=_mean([member.pv_dc_kw for member in members]),
                pv_ac_kw=_mean([member.pv_ac_kw for member in members]) or 0.0,
                pv_energy_kwh=sum(member.pv_energy_kwh for member in members),
                arrays=tuple(
                    PVArrayInterval(
                        array_id=array_id,
                        poa=_mean([item.poa for item in items]),
                        cell_temp_c=_mean([item.cell_temp_c for item in items]),
                        pv_dc_kw=_mean([item.pv_dc_kw for item in items]),
                        pv_ac_kw=_mean([item.pv_ac_kw for item in items]) or 0.0,
                        pv_energy_kwh=sum(item.pv_energy_kwh for item in items),
                    )
                    for array_id, items in sorted(arrays_by_id.items())
                ),
            )
        )
    return forecast.model_copy(
        update={"resolution_minutes": resolution_minutes, "intervals": tuple(intervals)}
    )
