"""A weather (irradiance) forecast provider: Open-Meteo, NOAA HRRR, ... Implementations live in
services/<provider>/provider.py and are the only code that knows a provider's URL, parameters,
field names, units or conventions."""

from typing import Protocol

from intelli_gateway.schemas.solar_forecast import (
    SiteConfig,
    WeatherForecast,
    WeatherProviderCapabilities,
)


class WeatherProvider(Protocol):
    @property
    def name(self) -> str: ...

    def capabilities(self) -> WeatherProviderCapabilities: ...

    async def fetch_forecast(
        self, site: SiteConfig, horizon_hours: int, resolution_minutes: int
    ) -> WeatherForecast:
        """Normalized weather for the site's location (and plane-of-array irradiance per array,
        if the provider computes it). Raises ProviderError on any failure."""
        ...

    async def health_check(self) -> bool: ...

    async def aclose(self) -> None: ...
