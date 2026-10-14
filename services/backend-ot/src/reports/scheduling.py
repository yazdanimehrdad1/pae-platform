"""
Turning due schedules into reports: every minute, each schedule whose time has come queues its
template's report (the worker generates it), moves on to its next time, and prunes its old reports.

- The report covers the window resolved at the occurrence's time, not at dispatch time, so a
  "yesterday" report due at 06:00 covers the same day even if the dispatch runs late.
- After downtime a schedule generates once (the latest missed occurrence), then continues from
  now: it never floods the queue with every missed occurrence.
- A template that no longer fits its site (a point deleted, say) records a failed report with the
  reason, so the schedule's failure shows in the reports list.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from helpers.common.date_time import resolve_timezone
from logger import get_logger
from reports import repository, schedule_repository
from reports.cadence import next_run_time
from reports.data_source import ReportDataSource
from reports.validation import definition_errors
from reports.windows import resolve_window, window_length_error
from schemas.reports.internal import DueSchedule

logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def dispatch_due_schedules(data_source: ReportDataSource, clock: Callable[[], datetime] = _utc_now) -> int:
    """Queue a report for every due schedule; returns how many occurrences it handled."""
    handled = 0
    for due in await schedule_repository.list_due_schedules(clock()):
        try:
            if await _dispatch(due, data_source, clock()):
                handled += 1
        except Exception as error:
            logger.error(f"Report schedule {due.schedule_id} failed to dispatch: {error}", exc_info=True)
    return handled


async def _dispatch(due: DueSchedule, data_source: ReportDataSource, now: datetime) -> bool:
    site = await data_source.get_site_context(due.site_id)
    site_timezone = resolve_timezone(site.site.timezone) if site is not None else resolve_timezone("UTC")
    # The next occurrence after now: missed ones in between are skipped (this one catches up).
    claimed = await schedule_repository.advance_schedule(
        due.schedule_id, due.due_at, next_run_time(due.cadence, site_timezone, max(now, due.due_at)),
    )
    if not claimed or site is None:
        return claimed  # another worker took it; or the site is gone (soft-deleted): nothing to report on

    start, end = resolve_window(due.definition.window, due.due_at, site_timezone)
    problems = definition_errors(due.definition, site)
    length_error = window_length_error(start, end)
    if length_error:
        problems.append(length_error)
    await repository.insert_run(
        due.site_id,
        name=due.template_name,
        definition=due.definition,
        window_start=start,
        window_end=end,
        trigger="schedule",
        template_id=due.template_id,
        template_version=due.template_version,
        schedule_id=due.schedule_id,
        failed_error=f"The template no longer fits the site: {'; '.join(problems)}" if problems else None,
    )
    pruned = await schedule_repository.prune_schedule_runs(due.schedule_id, due.keep_last, due.keep_days, now)
    logger.info(f"Report schedule {due.schedule_id} queued '{due.template_name}' for {due.due_at.isoformat()} (pruned {pruned})")
    return True
