"""The periodic forecast refresh: one asyncio task started in the app lifespan. It refreshes at
startup, then every interval. A failed run is logged and the next one still happens.
One uvicorn worker runs this service; with several replicas, give one of them the job only
(FORECAST_FETCH_INTERVAL_MINUTES=0 on the others)."""

import asyncio
import contextlib
import logging

from intelli_gateway.solar_forecast.service import ForecastService

logger = logging.getLogger(__name__)


class ForecastRefreshJob:
    def __init__(self, service: ForecastService, interval_minutes: int) -> None:
        self._service = service
        self._interval_s = interval_minutes * 60
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._interval_s <= 0 or self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="forecast-refresh")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                result = await self._service.refresh()
                failed = [site.site_id for site in result.sites if not site.ok]
                logger.info(
                    "forecast_refresh_run",
                    extra={"fields": {"sites": len(result.sites), "failed_sites": failed}},
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # never let one bad run end the job
                logger.exception("forecast_refresh_run_failed")
            await asyncio.sleep(self._interval_s)
