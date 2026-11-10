"""The periodic site profile sync: one asyncio task started in the app lifespan. It reads every
site's catalog from backend-ot at startup, then every interval, and stores it as pending changes
(it never approves anything). A failed run is retried after RETRY_AFTER_FAILURE_S, not the
whole interval: at startup the other services may still be starting.
With several replicas, give one of them the job only (SITE_PROFILE_SYNC_INTERVAL_MINUTES=0 on
the others)."""

import asyncio
import contextlib
import logging

from intelli_gateway.site_profile.service import SiteProfileService
from intelli_gateway.utils.exceptions import UpstreamUnavailableError

logger = logging.getLogger(__name__)

RETRY_AFTER_FAILURE_S = 30.0


class SiteProfileSyncJob:
    def __init__(
        self,
        service: SiteProfileService,
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
        self._task = asyncio.create_task(self._run(), name="site-profile-sync")

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
                await self._service.sync_all()
            except asyncio.CancelledError:
                raise
            except UpstreamUnavailableError as error:  # e.g. backend-ot still starting
                logger.warning(
                    "site_profile_sync_upstream_unavailable",
                    extra={"fields": {"error": str(error), "retry_in_s": self._retry_s}},
                )
                delay_s = self._retry_s
            except Exception:  # never let one bad run end the job
                logger.exception("site_profile_sync_run_failed")
                delay_s = self._retry_s
            await asyncio.sleep(delay_s)
