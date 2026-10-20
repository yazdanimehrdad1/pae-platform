"""Turns a normalized weather forecast into PV power. Provider-agnostic, so it is swappable too."""

from typing import Protocol

from intelli_gateway.schemas.solar_forecast import PVInterval, SiteConfig, WeatherForecast


class PvModel(Protocol):
    def compute(self, site: SiteConfig, weather: WeatherForecast) -> list[PVInterval]:
        """One PVInterval per weather interval: site totals plus the per-array breakdown."""
        ...
