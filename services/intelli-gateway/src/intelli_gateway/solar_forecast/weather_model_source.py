"""WeatherModelSource: a PvForecastSource made of a weather provider plus a PV model. The facade
sees a PV forecast source; it never learns that the kW came from this service's model."""

from intelli_gateway.interfaces.pv_model import PvModel
from intelli_gateway.interfaces.weather_provider import WeatherProvider
from intelli_gateway.schemas.solar_forecast import (
    PVForecast,
    SiteConfig,
    SourceCapabilities,
    SourceKind,
)


class WeatherModelSource:
    def __init__(self, provider: WeatherProvider, pv_model: PvModel) -> None:
        self._provider = provider
        self._pv_model = pv_model

    @property
    def name(self) -> str:
        return self._provider.name

    def capabilities(self) -> SourceCapabilities:
        weather = self._provider.capabilities()
        return SourceCapabilities(
            kind=SourceKind.WEATHER_MODEL,
            provides_weather=True,
            resolutions_minutes=weather.resolutions_minutes,
            max_horizon_hours=weather.max_horizon_hours,
            commercial_use_allowed=weather.commercial_use_allowed,
        )

    async def forecast(
        self, site: SiteConfig, horizon_hours: int, resolution_minutes: int
    ) -> PVForecast:
        weather = await self._provider.fetch_forecast(site, horizon_hours, resolution_minutes)
        return PVForecast(
            site_id=site.site_id,
            source_name=self.name,
            source_kind=SourceKind.WEATHER_MODEL,
            issued_at=weather.issued_at,
            resolution_minutes=weather.resolution_minutes,
            intervals=tuple(self._pv_model.compute(site, weather)),
        )

    async def health_check(self) -> bool:
        return await self._provider.health_check()

    async def aclose(self) -> None:
        await self._provider.aclose()
