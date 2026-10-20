"""Stored PV forecasts and the fetch log. Implementations: Postgres (services/postgres/) and in
memory (fake_data/forecast.py). Every refresh is kept (no overwrites), for backtesting."""

from datetime import datetime
from typing import Protocol

from intelli_gateway.schemas.solar_forecast import FetchLogEntry, PVForecast


class ForecastRepository(Protocol):
    async def save(self, forecast: PVForecast) -> None: ...

    async def latest(
        self, site_id: int, issued_before: datetime | None = None
    ) -> PVForecast | None:
        """The most recently issued forecast of the site; with issued_before, the newest one
        issued strictly before that time (what was known then)."""
        ...

    async def log_fetch(self, entry: FetchLogEntry) -> None: ...

    async def last_fetch(self, site_id: int, ok: bool | None = None) -> FetchLogEntry | None:
        """The newest fetch-log entry of the site; with ok, the newest success or failure."""
        ...

    async def delete_issued_before(self, cutoff: datetime) -> int:
        """Retention: drop forecasts issued before the cutoff (and older fetch-log entries)."""
        ...

    async def aclose(self) -> None: ...
