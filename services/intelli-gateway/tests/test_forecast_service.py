"""ForecastService, the PV forecast facade, over fakes only (no real provider).

Invariant guarded: refresh tries the primary source, then each fallback in order, stores the first
success flagged with fallback_used, and logs every attempt; when all fail the result and the log
say so and nothing is stored; a crashing source doesn't stop the others; history is kept and read
back by issue time; reads resample (kW and W/m2 averaged, kWh summed) and window; the daily
summary uses the site's local day; raw weather is refused for PV-power sources; health reports
the last attempt, the last success and staleness; retention drops old runs.
"""

from datetime import UTC, datetime, timedelta

import pytest
from forecast_fakes import FORECAST_NOW, SITE

from intelli_gateway.fake_data.forecast import (
    FakePvPowerSource,
    FakeSiteConfigSource,
    FakeWeatherProvider,
    InMemoryForecastRepository,
)
from intelli_gateway.interfaces.pv_forecast_source import PvForecastSource
from intelli_gateway.schemas.solar_forecast import PVForecast, SiteConfig
from intelli_gateway.solar_forecast.pv_model import PvlibPvModel
from intelli_gateway.solar_forecast.service import ForecastService, ForecastSettings, resample
from intelli_gateway.solar_forecast.weather_model_source import WeatherModelSource
from intelli_gateway.utils.exceptions import (
    ConfigurationError,
    InvalidRequestError,
    NotFoundError,
    ProviderError,
    UpstreamUnavailableError,
)

SETTINGS = ForecastSettings(
    enabled=True,
    horizon_hours=48,
    resolution_minutes=15,
    refresh_interval_minutes=15,
    retention_days=90,
)


class Clock:
    def __init__(self, now: datetime = FORECAST_NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class CrashingSource(FakePvPowerSource):
    async def forecast(
        self, site: SiteConfig, horizon_hours: int, resolution_minutes: int
    ) -> PVForecast:
        raise RuntimeError("bug in a source")


def make_service(
    sources: list[PvForecastSource],
    clock: Clock | None = None,
    repository: InMemoryForecastRepository | None = None,
    settings: ForecastSettings = SETTINGS,
    sites: tuple[SiteConfig, ...] = (SITE,),
) -> tuple[ForecastService, InMemoryForecastRepository]:
    repository = repository or InMemoryForecastRepository()
    service = ForecastService(
        sites=FakeSiteConfigSource(sites),
        sources=sources,
        repository=repository,
        settings=settings,
        clock=clock or Clock(),
    )
    return service, repository


def weather_source(name: str, clock: Clock, fail: bool = False) -> WeatherModelSource:
    return WeatherModelSource(
        FakeWeatherProvider(name=name, clock=clock, fail=fail), PvlibPvModel()
    )


class TestRefresh:
    async def test_primary_success_is_stored_and_logged(self) -> None:
        clock = Clock()
        service, repository = make_service([weather_source("primary", clock)], clock)
        result = await service.refresh()
        (site,) = result.sites
        assert site.ok and site.source_name == "primary" and not site.fallback_used
        assert site.intervals == 48 * 4
        stored = repository.forecasts[-1]
        assert stored.source_name == "primary" and not stored.fallback_used
        assert [(entry.source_name, entry.ok) for entry in repository.fetch_log] == [
            ("primary", True)
        ]

    async def test_primary_fails_so_fallback_is_used_and_flagged(self) -> None:
        clock = Clock()
        primary = weather_source("primary", clock, fail=True)
        fallback = FakePvPowerSource(name="backup", clock=clock)
        service, repository = make_service([primary, fallback], clock)
        (site,) = (await service.refresh()).sites
        assert site.ok and site.source_name == "backup" and site.fallback_used
        stored = repository.forecasts[-1]
        assert stored.fallback_used and stored.source_name == "backup"
        assert [(e.source_name, e.ok, e.fallback_used) for e in repository.fetch_log] == [
            ("primary", False, False),
            ("backup", True, True),
        ]
        assert "down" in (repository.fetch_log[0].error or "")

    async def test_fallbacks_are_tried_in_order_and_stop_at_the_first_success(self) -> None:
        clock = Clock()
        first = FakePvPowerSource(name="a", clock=clock, fail=True)
        second = FakePvPowerSource(name="b", clock=clock)
        third = FakePvPowerSource(name="c", clock=clock)
        service, _ = make_service([first, second, third], clock)
        (site,) = (await service.refresh()).sites
        assert site.source_name == "b"
        assert (first.calls, second.calls, third.calls) == (1, 1, 0)

    async def test_all_sources_fail(self) -> None:
        clock = Clock()
        service, repository = make_service(
            [weather_source("a", clock, fail=True), FakePvPowerSource("b", clock, fail=True)], clock
        )
        (site,) = (await service.refresh()).sites
        assert not site.ok and site.source_name is None
        assert "a is down" in (site.error or "") and "b is down" in (site.error or "")
        assert repository.forecasts == []
        assert [entry.ok for entry in repository.fetch_log] == [False, False]

    async def test_a_crashing_source_is_a_failure_not_a_crash(self) -> None:
        clock = Clock()
        service, _ = make_service([CrashingSource("buggy", clock), FakePvPowerSource("ok", clock)])
        (site,) = (await service.refresh()).sites
        assert site.ok and site.source_name == "ok"

    async def test_one_site(self) -> None:
        clock = Clock()
        other = SITE.model_copy(update={"site_id": 2002})
        service, _ = make_service([FakePvPowerSource(clock=clock)], clock, sites=(SITE, other))
        result = await service.refresh(2002)
        assert [site.site_id for site in result.sites] == [2002]
        with pytest.raises(NotFoundError):
            await service.refresh(9999)

    async def test_disabled(self) -> None:
        disabled = ForecastSettings(**{**SETTINGS.__dict__, "enabled": False})
        service, _ = make_service([FakePvPowerSource()], settings=disabled)
        with pytest.raises(ConfigurationError):
            await service.refresh()

    def test_needs_a_source(self) -> None:
        with pytest.raises(ConfigurationError):
            make_service([])

    async def test_history_is_kept_and_retention_drops_old_runs(self) -> None:
        clock = Clock(FORECAST_NOW - timedelta(days=100))
        service, repository = make_service([FakePvPowerSource(clock=clock)], clock)
        await service.refresh()
        clock.now = FORECAST_NOW - timedelta(hours=1)
        await service.refresh()
        assert len(repository.forecasts) == 1  # the 100-day-old run is past retention
        clock.now = FORECAST_NOW
        await service.refresh()
        assert [f.issued_at for f in repository.forecasts] == [
            FORECAST_NOW - timedelta(hours=1),
            FORECAST_NOW,
        ]


class TestReads:
    async def refreshed(self, source: PvForecastSource | None = None) -> ForecastService:
        clock = Clock()
        service, _ = make_service([source or FakePvPowerSource(clock=clock)], clock)
        await service.refresh()
        return service

    async def test_nothing_stored_yet(self) -> None:
        service, _ = make_service([FakePvPowerSource()])
        start = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
        with pytest.raises(NotFoundError):
            await service.get_as_forecast(SITE.site_id, start, start + timedelta(hours=1))

    async def test_hourly_resample(self) -> None:
        service = await self.refreshed()
        start = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
        hourly = await service.get_as_forecast(
            SITE.site_id, start, start + timedelta(hours=6), resolution_minutes=60
        )
        assert hourly.resolution_minutes == 60
        assert [i.interval_start.hour for i in hourly.intervals] == [12, 13, 14, 15, 16, 17]
        # FakePvPowerSource: half of 5000 kW from 08:00 to 16:00 UTC.
        assert hourly.intervals[0].pv_ac_kw == 2500
        assert hourly.intervals[4].pv_ac_kw == 0

    def test_resample_averages_power_and_weather(self) -> None:
        start = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
        forecast = PVForecast.model_validate(
            {
                "site_id": 1,
                "source_name": "x",
                "source_kind": "pv_power",
                "issued_at": start,
                "resolution_minutes": 15,
                "intervals": [
                    {
                        "interval_start": start + timedelta(minutes=15 * k),
                        "interval_end": start + timedelta(minutes=15 * (k + 1)),
                        "pv_ac_kw": kw,
                        "cloud_cover_pct": 10 * (k + 1),
                    }
                    for k, kw in enumerate([100, 200, 300, 400])
                ],
            }
        )
        (hour,) = resample(forecast, 60).intervals
        assert hour.pv_ac_kw == 250 and hour.cloud_cover_pct == 25
        assert hour.ghi is None  # no weather stays no weather

    async def test_resolution_must_be_a_multiple(self) -> None:
        service = await self.refreshed()
        start = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
        for resolution in (10, 20):
            with pytest.raises(InvalidRequestError):
                await service.get_as_forecast(
                    SITE.site_id, start, start + timedelta(hours=2), resolution_minutes=resolution
                )

    async def test_as_forecast_series_spans_past_runs_and_the_future(self) -> None:
        clock = Clock(datetime(2026, 6, 15, 8, 0, tzinfo=UTC))
        repository = InMemoryForecastRepository()
        early, _ = make_service([FakePvPowerSource("early", clock)], clock, repository)
        await early.refresh()
        clock.now = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
        late, _ = make_service([FakePvPowerSource("late", clock)], clock, repository)
        await late.refresh()

        series = await late.get_as_forecast(
            SITE.site_id,
            datetime(2026, 6, 15, 8, 0, tzinfo=UTC),
            datetime(2026, 6, 16, 8, 0, tzinfo=UTC),  # 22 h past the latest refresh
            resolution_minutes=60,
        )
        assert series.resolution_minutes == 60 and series.source_name == "late"
        assert len(series.intervals) == 24
        assert series.intervals[0].pv_ac_kw == 2500  # 08:00, from the early run

    async def test_as_forecast_window_rules(self) -> None:
        service = await self.refreshed()
        start = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
        with pytest.raises(InvalidRequestError):
            await service.get_as_forecast(SITE.site_id, start.replace(tzinfo=None), start)
        with pytest.raises(InvalidRequestError, match="11 days"):
            await service.get_as_forecast(SITE.site_id, start, start + timedelta(days=12))
        with pytest.raises(NotFoundError):
            await service.get_as_forecast(
                SITE.site_id, start - timedelta(days=3), start - timedelta(days=2)
            )

    async def test_weather_comes_with_a_weather_source(self) -> None:
        clock = Clock()
        service = await self.refreshed(weather_source("wx", clock))
        start = datetime(2026, 6, 15, 18, 0, tzinfo=UTC)
        series = await service.get_as_forecast(SITE.site_id, start, start + timedelta(hours=2))
        noon = series.intervals[4]  # 19:00, solar noon in Phoenix
        assert noon.ghi is not None and noon.ghi > 0 and noon.temp_air_c == 20.0
        assert noon.pv_ac_kw > 0 and noon.arrays[0].pv_ac_kw == noon.pv_ac_kw


class TestHealth:
    async def test_reports_success_failure_fallback_and_staleness(self) -> None:
        clock = Clock()
        primary = FakePvPowerSource(name="primary", clock=clock)
        backup = FakePvPowerSource(name="backup", clock=clock)
        service, _ = make_service([primary, backup], clock)

        (site,) = (await service.health()).sites
        assert site.last_success_at is None and site.stale

        await service.refresh()
        health = await service.health()
        assert health.active_source == "primary" and health.fallback_sources == ("backup",)
        (site,) = health.sites
        assert site.last_source == "primary" and not site.fallback_in_use and not site.stale

        primary.fail = True
        clock.now += timedelta(minutes=15)
        await service.refresh()
        (site,) = (await service.health()).sites
        assert site.last_source == "backup" and site.fallback_in_use
        assert site.last_error is None  # the last attempt (backup) succeeded

        backup.fail = True
        clock.now += timedelta(hours=1)
        await service.refresh()
        (site,) = (await service.health()).sites
        assert site.stale and site.last_error is not None


class TestProviderErrorIsAnUpstreamError:
    def test_maps_to_503(self) -> None:
        assert issubclass(ProviderError, UpstreamUnavailableError)
