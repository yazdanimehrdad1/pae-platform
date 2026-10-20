"""The one seam the PV forecast facade depends on. A source is either a weather provider plus this
service's PV model (solar_forecast/weather_model_source.py), or a PV-power prediction API that
returns kW itself (services/<name>/source.py). Either way it returns a normalized PVForecast."""

from typing import Protocol

from intelli_gateway.schemas.solar_forecast import PVForecast, SiteConfig, SourceCapabilities


class PvForecastSource(Protocol):
    @property
    def name(self) -> str: ...

    def capabilities(self) -> SourceCapabilities: ...

    async def forecast(
        self, site: SiteConfig, horizon_hours: int, resolution_minutes: int
    ) -> PVForecast:
        """Raises ProviderError on any failure (upstream down, bad payload, unsupported request)."""
        ...

    async def health_check(self) -> bool: ...

    async def aclose(self) -> None: ...
