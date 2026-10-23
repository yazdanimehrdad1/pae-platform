"""The provider contracts every forecast source must pass, run against every implementation.

Invariant guarded: a WeatherProvider returns a WeatherForecast for the asked site with aware UTC,
explicit, contiguous intervals of the asked resolution inside the horizon, SI values, POA only
for the site's arrays, and raises ProviderError for every failure (HTTP error, bad payload,
timeout, unsupported request). A PvForecastSource returns a PVForecast of its own name and kind,
with non-negative AC power clipped at the site's AC capacity (the sum of its arrays), and weather
exactly when it says it provides weather. A new source is added to CASES here and must pass
unchanged.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, timedelta
from typing import Protocol, TypeVar

import pytest
from forecast_fakes import (
    SITE,
    TWO_PLANE_SITE,
    failing_open_meteo,
    fixed_now,
    open_meteo_provider,
)

from intelli_gateway.fake_data.forecast import FakePvPowerSource, FakeWeatherProvider
from intelli_gateway.interfaces.pv_forecast_source import PvForecastSource
from intelli_gateway.interfaces.weather_provider import WeatherProvider
from intelli_gateway.schemas.solar_forecast import PVForecast, SiteConfig, WeatherForecast
from intelli_gateway.solar_forecast.pv_model import PvlibPvModel
from intelli_gateway.solar_forecast.weather_model_source import WeatherModelSource
from intelli_gateway.utils.exceptions import ProviderError

HORIZON_HOURS = 48
RESOLUTION = 15


@dataclass(frozen=True)
class WeatherCase:
    name: str
    make: Callable[[], WeatherProvider]
    failing: tuple[Callable[[], WeatherProvider], ...]


@dataclass(frozen=True)
class SourceCase:
    name: str
    make: Callable[[], PvForecastSource]
    failing: Callable[[], PvForecastSource]


WEATHER_CASES = [
    WeatherCase(
        "open_meteo",
        open_meteo_provider,
        (
            lambda: failing_open_meteo(503),
            lambda: failing_open_meteo(400),
            lambda: failing_open_meteo(None),
            lambda: failing_open_meteo(body=b'{"daily": {}}'),
            lambda: failing_open_meteo(body=b"not json"),
        ),
    ),
    WeatherCase(
        "fake_weather",
        lambda: FakeWeatherProvider(clock=fixed_now),
        (lambda: FakeWeatherProvider(clock=fixed_now, fail=True),),
    ),
]

SOURCE_CASES = [
    SourceCase(
        "open_meteo+pvlib",
        lambda: WeatherModelSource(open_meteo_provider(), PvlibPvModel()),
        lambda: WeatherModelSource(failing_open_meteo(503), PvlibPvModel()),
    ),
    SourceCase(
        "fake_weather+pvlib",
        lambda: WeatherModelSource(FakeWeatherProvider(clock=fixed_now), PvlibPvModel()),
        lambda: WeatherModelSource(FakeWeatherProvider(clock=fixed_now, fail=True), PvlibPvModel()),
    ),
    SourceCase(
        "fake_pv_power",
        lambda: FakePvPowerSource(clock=fixed_now),
        lambda: FakePvPowerSource(clock=fixed_now, fail=True),
    ),
]


class _Closable(Protocol):
    async def aclose(self) -> None: ...


ClosableT = TypeVar("ClosableT", bound=_Closable)


async def _closing(
    make: Callable[[], ClosableT], use: Callable[[ClosableT], Awaitable[None]]
) -> None:
    instance = make()
    try:
        await use(instance)
    finally:
        await instance.aclose()


def check_intervals(
    forecast: WeatherForecast | PVForecast, resolution: int, horizon_hours: int
) -> None:
    intervals = forecast.intervals
    assert intervals
    step = timedelta(minutes=resolution)
    for interval in intervals:
        assert interval.interval_start.utcoffset() == timedelta(0)
        assert interval.interval_start.tzinfo is not None
        assert interval.interval_end - interval.interval_start == step
    for earlier, later in zip(intervals, intervals[1:], strict=False):
        assert later.interval_start == earlier.interval_end  # contiguous, sorted
    assert intervals[0].interval_end > forecast.issued_at
    assert intervals[-1].interval_start < forecast.issued_at + timedelta(hours=horizon_hours)
    assert forecast.issued_at.tzinfo is not None
    assert forecast.issued_at.astimezone(UTC) == forecast.issued_at


@pytest.mark.parametrize("case", WEATHER_CASES, ids=lambda case: case.name)
class TestWeatherProviderContract:
    async def test_returns_a_normalized_forecast(self, case: WeatherCase) -> None:
        async def use(provider: WeatherProvider) -> None:
            weather = await provider.fetch_forecast(TWO_PLANE_SITE, HORIZON_HOURS, RESOLUTION)
            assert weather.site_id == TWO_PLANE_SITE.site_id
            assert weather.provider_name == provider.name
            assert weather.resolution_minutes == RESOLUTION
            check_intervals(weather, RESOLUTION, HORIZON_HOURS)
            array_ids = {array.array_id for array in TWO_PLANE_SITE.arrays}
            for interval in weather.intervals:
                assert interval.ghi >= 0 and interval.dni >= 0 and interval.dhi >= 0
                assert interval.wind_speed_ms >= 0
                assert -60 < interval.temp_air_c < 70
                assert set(interval.poa_by_array) <= array_ids
            if provider.capabilities().provides_poa:
                assert any(interval.poa_by_array for interval in weather.intervals)

        await _closing(case.make, use)

    async def test_hourly_resolution(self, case: WeatherCase) -> None:
        async def use(provider: WeatherProvider) -> None:
            if 60 not in provider.capabilities().resolutions_minutes:
                pytest.skip("provider has no hourly data")
            weather = await provider.fetch_forecast(SITE, 24, 60)
            check_intervals(weather, 60, 24)

        await _closing(case.make, use)

    async def test_unsupported_resolution_is_a_provider_error(self, case: WeatherCase) -> None:
        async def use(provider: WeatherProvider) -> None:
            if 7 in provider.capabilities().resolutions_minutes:
                pytest.skip("provider supports 7-minute data")
            if isinstance(provider, FakeWeatherProvider):
                pytest.skip("the fake accepts any resolution")
            with pytest.raises(ProviderError):
                await provider.fetch_forecast(SITE, 24, 7)

        await _closing(case.make, use)

    async def test_every_failure_is_a_provider_error(self, case: WeatherCase) -> None:
        for make_failing in case.failing:

            async def use(provider: WeatherProvider) -> None:
                with pytest.raises(ProviderError):
                    await provider.fetch_forecast(SITE, HORIZON_HOURS, RESOLUTION)

            await _closing(make_failing, use)


def check_pv_forecast(forecast: PVForecast, source: PvForecastSource, site: SiteConfig) -> None:
    capabilities = source.capabilities()
    assert forecast.site_id == site.site_id
    assert forecast.source_name == source.name
    assert forecast.source_kind == capabilities.kind
    assert forecast.fallback_used is False  # only the facade sets it
    check_intervals(forecast, RESOLUTION, HORIZON_HOURS)
    array_ids = {array.array_id for array in site.arrays}
    for interval in forecast.intervals:
        assert 0 <= interval.pv_ac_kw <= site.ac_capacity_kw + 1e-6
        assert {array.array_id for array in interval.arrays} <= array_ids
        if interval.arrays:
            assert interval.pv_ac_kw == pytest.approx(sum(a.pv_ac_kw for a in interval.arrays))
        has_weather = interval.ghi is not None and interval.temp_air_c is not None
        assert has_weather == capabilities.provides_weather
    assert any(interval.pv_ac_kw > 0 for interval in forecast.intervals)


@pytest.mark.parametrize("case", SOURCE_CASES, ids=lambda case: case.name)
class TestPvForecastSourceContract:
    async def test_returns_a_normalized_pv_forecast(self, case: SourceCase) -> None:
        async def use(source: PvForecastSource) -> None:
            forecast = await source.forecast(TWO_PLANE_SITE, HORIZON_HOURS, RESOLUTION)
            check_pv_forecast(forecast, source, TWO_PLANE_SITE)

        await _closing(case.make, use)

    async def test_failure_is_a_provider_error(self, case: SourceCase) -> None:
        async def use(source: PvForecastSource) -> None:
            with pytest.raises(ProviderError):
                await source.forecast(SITE, HORIZON_HOURS, RESOLUTION)

        await _closing(case.failing, use)
