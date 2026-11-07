"""The periodic site profile sync: one asyncio task started in the app lifespan. It reads every
site's catalog from backend-ot at startup, then every interval, and stores it as pending changes
(it never approves anything). A failed run is logged and the next one still happens.
With several replicas, give one of them the job only (SITE_PROFILE_SYNC_INTERVAL_MINUTES=0 on
the others)."""

import asyncio
import contextlib
import logging

from intelli_gateway.site_profile.service import SiteProfileService

logger = logging.getLogger(__name__)


class SiteProfileSyncJob:
    def __init__(self, service: SiteProfileService, interval_minutes: int) -> None:
        self._service = service
        self._interval_s = interval_minutes * 60
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
            try:
                await self._service.sync_all()
            except asyncio.CancelledError:
                raise
            except Exception:  # never let one bad run end the job
                logger.exception("site_profile_sync_run_failed")
            await asyncio.sleep(self._interval_s)
