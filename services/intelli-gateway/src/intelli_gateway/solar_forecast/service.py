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
from datetime import UTC, datetime, timedelta

from intelli_gateway.interfaces.forecast_repository import ForecastRepository
from intelli_gateway.interfaces.pv_forecast_source import PvForecastSource
from intelli_gateway.interfaces.site_config_source import SiteConfigSource
from intelli_gateway.schemas.solar_forecast import (
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
# The as-forecast read spans at most this (a 7-day history plus the 72-hour horizon fits).
MAX_AS_FORECAST_WINDOW = timedelta(days=11)


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
        stored as a new run. Then forecasts past retention are dropped."""
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

    async def get_as_forecast(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        resolution_minutes: int | None = None,
    ) -> PVForecast:
        """One continuous series over [start, end): each interval as forecast just before it
        began (the newest run issued at or before its start), so the past can be compared with
        actual output and the future is the latest forecast. resolution_minutes (a multiple of
        the stored one) averages it into coarser intervals."""
        _check_window(start, end)
        if end - start > MAX_AS_FORECAST_WINDOW:
            raise InvalidRequestError(
                f"the window may span at most {MAX_AS_FORECAST_WINDOW.days} days"
            )
        forecast = await self._repository.as_forecast(site_id, start, end)
        if forecast is None:
            raise NotFoundError(f"no forecast stored for site {site_id} in that window")
        return resample(forecast, resolution_minutes or forecast.resolution_minutes)

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


# --- pure helpers -------------------------------------------------------------------------


def _check_window(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or end.tzinfo is None:
        raise InvalidRequestError("start and end must carry a timezone offset")
    if end <= start:
        raise InvalidRequestError("end must be after start")


def _mean(values: Sequence[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None


def resample(forecast: PVForecast, resolution_minutes: int) -> PVForecast:
    """Coarser intervals, aligned to the UTC clock: every value is the mean of the intervals
    in the bucket. The target must be a whole multiple of the stored resolution."""
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
                pv_ac_kw=_mean([member.pv_ac_kw for member in members]) or 0.0,
                ghi=_mean([member.ghi for member in members]),
                temp_air_c=_mean([member.temp_air_c for member in members]),
                wind_speed_ms=_mean([member.wind_speed_ms for member in members]),
                cloud_cover_pct=_mean([member.cloud_cover_pct for member in members]),
                arrays=tuple(
                    PVArrayInterval(
                        array_id=array_id,
                        pv_ac_kw=_mean([item.pv_ac_kw for item in items]) or 0.0,
                    )
                    for array_id, items in sorted(arrays_by_id.items())
                ),
            )
        )
    return forecast.model_copy(
        update={"resolution_minutes": resolution_minutes, "intervals": tuple(intervals)}
    )
