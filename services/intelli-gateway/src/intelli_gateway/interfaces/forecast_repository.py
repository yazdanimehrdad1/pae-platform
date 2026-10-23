"""Stored PV forecasts and the fetch log. Implementations: Postgres (services/postgres/) and in
memory (fake_data/forecast.py). Each refresh is a new run; saving it prunes the older runs'
rows it supersedes, so each interval keeps only the forecast that was current when it began."""

from datetime import datetime
from typing import Protocol

from intelli_gateway.schemas.solar_forecast import FetchLogEntry, PVForecast


class ForecastRepository(Protocol):
    async def save(self, forecast: PVForecast) -> None:
        """Store the run, and delete the older runs' intervals starting at or after its issue
        time (as_forecast would never read them again), plus runs left without intervals."""
        ...

    async def as_forecast(self, site_id: int, start: datetime, end: datetime) -> PVForecast | None:
        """The as-forecast series over intervals starting in [start, end): each interval taken
        from the newest run issued at or before its start (so a past interval shows what was
        forecast just before it, a future one the latest forecast). Source, kind and issued_at
        are the newest run used. None when no run covers the window."""
        ...

    async def log_fetch(self, entry: FetchLogEntry) -> None: ...

    async def last_fetch(self, site_id: int, ok: bool | None = None) -> FetchLogEntry | None:
        """The newest fetch-log entry of the site; with ok, the newest success or failure."""
        ...

    async def delete_issued_before(self, cutoff: datetime) -> int:
        """Retention: drop forecasts issued before the cutoff (and older fetch-log entries)."""
        ...

    async def aclose(self) -> None: ...
