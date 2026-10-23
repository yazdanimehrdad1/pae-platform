"""Forecast source registry: config name -> factory. Adding a source = its file in
services/<name>/ + one entry here + config (FORECAST_SOURCE / FORECAST_FALLBACK_SOURCES).
A source's own settings (OPEN_METEO_*, ...) are read only when it is selected."""

from collections.abc import Callable
from datetime import datetime

from intelli_gateway.config import Settings
from intelli_gateway.fake_data.forecast import FakePvPowerSource, FakeWeatherProvider
from intelli_gateway.interfaces.pv_forecast_source import PvForecastSource
from intelli_gateway.services.noaa_hrrr.provider import NoaaHrrrProvider
from intelli_gateway.services.open_meteo.provider import OpenMeteoProvider
from intelli_gateway.solar_forecast.pv_model import PvlibPvModel
from intelli_gateway.solar_forecast.weather_model_source import WeatherModelSource
from intelli_gateway.utils.exceptions import ConfigurationError

Clock = Callable[[], datetime]
SourceFactory = Callable[[Settings, Clock], PvForecastSource]


def _open_meteo(settings: Settings, clock: Clock) -> PvForecastSource:
    provider = OpenMeteoProvider(
        base_url=settings.open_meteo_base_url,
        api_key=settings.open_meteo_api_key,
        timeout_s=settings.open_meteo_timeout_s,
        attempts=settings.open_meteo_retries,
        max_calls_per_minute=settings.open_meteo_max_calls_per_minute,
        clock=clock,
    )
    return WeatherModelSource(provider, PvlibPvModel())


def _noaa_hrrr(settings: Settings, clock: Clock) -> PvForecastSource:
    del settings, clock
    return WeatherModelSource(NoaaHrrrProvider(), PvlibPvModel())


def _fake(settings: Settings, clock: Clock) -> PvForecastSource:
    del settings
    return WeatherModelSource(FakeWeatherProvider(name="fake", clock=clock), PvlibPvModel())


def _fake_pv_power(settings: Settings, clock: Clock) -> PvForecastSource:
    del settings
    return FakePvPowerSource(name="fake_pv_power", clock=clock)


SOURCES: dict[str, SourceFactory] = {
    "open_meteo": _open_meteo,
    "noaa_hrrr": _noaa_hrrr,
    "fake": _fake,  # offline clear-sky weather + the PV model
    "fake_pv_power": _fake_pv_power,  # offline PV-power API stand-in
}


def build_sources(settings: Settings, clock: Clock) -> list[PvForecastSource]:
    """The primary source, then each fallback in order (duplicates dropped)."""
    names: list[str] = []
    for name in (settings.forecast_source, *settings.forecast_fallback_sources):
        if name not in SOURCES:
            raise ConfigurationError(
                f"unknown forecast source {name!r}; known: {', '.join(sorted(SOURCES))}"
            )
        if name not in names:
            names.append(name)
    return [SOURCES[name](settings, clock) for name in names]
