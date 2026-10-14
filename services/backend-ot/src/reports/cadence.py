"""When a schedule next generates: its cadence, on the site's clock. Pure (the caller passes the time)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from schemas.reports.schedules import (
    DailyCadence,
    HourlyCadence,
    MonthlyCadence,
    ReportCadence,
    WeeklyCadence,
)

_WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def cadence_trigger(cadence: ReportCadence, site_timezone: ZoneInfo) -> CronTrigger:
    """The cadence as a cron trigger in the site's zone (APScheduler applies DST)."""
    match cadence:
        case HourlyCadence(minute=minute):
            return CronTrigger(minute=minute, timezone=site_timezone)
        case DailyCadence(time=time):
            hour, minute = _hour_minute(time)
            return CronTrigger(hour=hour, minute=minute, timezone=site_timezone)
        case WeeklyCadence(time=time, weekdays=weekdays):
            hour, minute = _hour_minute(time)
            days = ",".join(_WEEKDAY_NAMES[day] for day in weekdays)
            return CronTrigger(day_of_week=days, hour=hour, minute=minute, timezone=site_timezone)
        case MonthlyCadence(time=time, day_of_month=day):
            hour, minute = _hour_minute(time)
            return CronTrigger(day=day, hour=hour, minute=minute, timezone=site_timezone)
    raise ValueError(f"Unknown cadence: {cadence!r}")


def next_run_time(cadence: ReportCadence, site_timezone: ZoneInfo, after: datetime) -> datetime:
    """The first time the cadence fires strictly after `after`, in UTC."""
    fire_time = cadence_trigger(cadence, site_timezone).get_next_fire_time(None, after + timedelta(seconds=1))
    if fire_time is None:  # a cron cadence always fires again
        raise ValueError(f"Cadence {cadence!r} never fires after {after}")
    return fire_time.astimezone(UTC)


def _hour_minute(time: str) -> tuple[int, int]:
    hour, minute = time.split(":")
    return int(hour), int(minute)
