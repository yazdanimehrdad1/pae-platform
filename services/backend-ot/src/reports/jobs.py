"""The reports module's scheduler jobs, registered by scheduler/engine.py through its add_job:
report_schedule_dispatch queues the reports of due schedules, report_worker generates queued reports."""

from collections.abc import Callable
from typing import Any

from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from reports.backend_ot_source import BackendOtReportSource
from reports.scheduling import dispatch_due_schedules
from reports.worker import process_queued_runs

REPORT_WORKER_JOB_ID = "report_worker"
REPORT_SCHEDULE_JOB_ID = "report_schedule_dispatch"


async def cron_job_generate_queued_reports() -> None:
    await process_queued_runs(BackendOtReportSource())


async def cron_job_dispatch_report_schedules() -> None:
    await dispatch_due_schedules(BackendOtReportSource())


def register_report_jobs(add_job: Callable[..., Any]) -> None:
    """Both jobs run on the leader only, like every job."""
    add_job(
        job_func=cron_job_generate_queued_reports,
        trigger=IntervalTrigger(seconds=settings.report_worker_interval_seconds),
        job_id=REPORT_WORKER_JOB_ID,
        name="Report Generation",
    )
    add_job(
        job_func=cron_job_dispatch_report_schedules,
        trigger=IntervalTrigger(seconds=settings.report_schedule_interval_seconds),
        job_id=REPORT_SCHEDULE_JOB_ID,
        name="Report Schedules",
    )
