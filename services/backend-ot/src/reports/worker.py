"""Generating queued reports: claim a queued run, generate its snapshot, store it (or the error)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from logger import get_logger
from reports import repository
from reports.data_source import ReportDataSource
from reports.generate import generate_snapshot

logger = get_logger(__name__)

STALE_RUN_AFTER = timedelta(minutes=15)


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def process_queued_runs(
    data_source: ReportDataSource, max_runs: int = 5, clock: Callable[[], datetime] = _utc_now
) -> int:
    """Generate up to `max_runs` queued reports, oldest first; returns how many it finished. Runs
    left 'running' by a worker that stopped are failed first, so they don't stay running forever."""
    stale = await repository.fail_stale_runs(clock() - STALE_RUN_AFTER, clock())
    if stale:
        logger.warning(f"Failed {stale} report run(s) interrupted while generating")
    finished = 0
    for _ in range(max_runs):
        run_id = await repository.claim_next_queued_run(clock())
        if run_id is None:
            break
        await execute_run(run_id, data_source, clock)
        finished += 1
    return finished


async def execute_run(run_id: int, data_source: ReportDataSource, clock: Callable[[], datetime] = _utc_now) -> None:
    """Generate one claimed run and store the outcome. Never raises: a failure is stored on the run."""
    try:
        run = await repository.get_run_by_id(run_id)
        if run is None:
            return
        site = await data_source.get_site_context(run.site_id)
        if site is None:
            await repository.finish_run(run_id, clock(), error=f"Site {run.site_id} no longer exists")
            return
        snapshot = await generate_snapshot(
            run.definition, site, run.window_start, run.window_end, clock(), data_source
        )
        await repository.finish_run(run_id, clock(), result=snapshot)
        logger.info(f"Report run {run_id} generated ({len(snapshot.blocks)} blocks)")
    except Exception as error:
        logger.error(f"Report run {run_id} failed: {error}", exc_info=True)
        await repository.finish_run(run_id, clock(), error="Report generation failed")
