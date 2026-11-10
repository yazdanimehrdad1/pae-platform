"""The periodic forecast refresh: one asyncio task started in the app lifespan. It refreshes at
startup, then every interval. A failed run is retried after RETRY_AFTER_FAILURE_S, not the whole
interval: at startup the other services may still be starting.
One uvicorn worker runs this service; with several replicas, give one of them the job only
(FORECAST_FETCH_INTERVAL_MINUTES=0 on the others)."""

import asyncio
import contextlib
import logging

from intelli_gateway.solar_forecast.service import ForecastService
from intelli_gateway.utils.exceptions import UpstreamUnavailableError

logger = logging.getLogger(__name__)

RETRY_AFTER_FAILURE_S = 30.0


class ForecastRefreshJob:
    def __init__(
        self,
        service: ForecastService,
        interval_minutes: int,
        retry_after_failure_s: float = RETRY_AFTER_FAILURE_S,
    ) -> None:
        self._service = service
        self._interval_s = interval_minutes * 60
        self._retry_s = min(retry_after_failure_s, self._interval_s)
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
            delay_s = self._interval_s
            try:
                result = await self._service.refresh()
                failed = [site.site_id for site in result.sites if not site.ok]
                logger.info(
                    "forecast_refresh_run",
                    extra={"fields": {"sites": len(result.sites), "failed_sites": failed}},
                )
            except asyncio.CancelledError:
                raise
            except UpstreamUnavailableError as error:  # e.g. backend-ot still starting
                logger.warning(
                    "forecast_refresh_upstream_unavailable",
                    extra={"fields": {"error": str(error), "retry_in_s": self._retry_s}},
                )
                delay_s = self._retry_s
            except Exception:  # never let one bad run end the job
                logger.exception("forecast_refresh_run_failed")
                delay_s = self._retry_s
            await asyncio.sleep(delay_s)
