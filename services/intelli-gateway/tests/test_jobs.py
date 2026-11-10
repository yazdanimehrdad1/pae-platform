"""The periodic jobs (site profile sync, forecast refresh) and a failed run.

Invariant guarded: a run that fails (backend-ot still starting, or any error) is retried after
the short retry delay, not after the whole interval, and the job keeps running; a run that
succeeds waits the full interval.
"""

import asyncio
from typing import Any, cast

from intelli_gateway.site_profile.scheduler import SiteProfileSyncJob
from intelli_gateway.solar_forecast.scheduler import ForecastRefreshJob
from intelli_gateway.utils.exceptions import BackendOtError

RETRY_S = 0.01  # the interval is a minute: only a retry can make a second call in this test


class FlakyService:
    """Fails the first `failures` calls, then succeeds."""

    def __init__(self, failures: list[Exception]) -> None:
        self._failures = failures
        self.calls = 0

    async def _call(self) -> Any:
        self.calls += 1
        if self._failures:
            raise self._failures.pop(0)
        return type("Result", (), {"sites": []})()

    async def sync_all(self) -> Any:
        return await self._call()

    async def refresh(self) -> Any:
        return await self._call()


async def wait_for_calls(service: FlakyService, count: int) -> None:
    async with asyncio.timeout(2):
        while service.calls < count:
            await asyncio.sleep(0.005)


async def test_the_sync_retries_soon_after_backend_ot_was_unreachable() -> None:
    service = FlakyService([BackendOtError("backend-ot unreachable (ConnectError)")])
    job = SiteProfileSyncJob(cast(Any, service), interval_minutes=1, retry_after_failure_s=RETRY_S)
    job.start()
    try:
        await wait_for_calls(service, 2)  # the retry, well before a minute
        await asyncio.sleep(0.05)
        assert service.calls == 2  # after a success: the full interval
    finally:
        await job.stop()


async def test_the_forecast_retries_soon_after_any_failure() -> None:
    service = FlakyService([RuntimeError("boom"), BackendOtError("unreachable")])
    job = ForecastRefreshJob(cast(Any, service), interval_minutes=1, retry_after_failure_s=RETRY_S)
    job.start()
    try:
        await wait_for_calls(service, 3)
        await asyncio.sleep(0.05)
        assert service.calls == 3
    finally:
        await job.stop()


def test_a_disabled_job_never_starts() -> None:
    job = SiteProfileSyncJob(cast(Any, FlakyService([])), interval_minutes=0)
    job.start()
    assert job._task is None  # pyright: ignore[reportPrivateUsage]
