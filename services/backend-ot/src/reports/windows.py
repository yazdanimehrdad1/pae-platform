"""Resolving a report window to UTC bounds. Pure: the caller passes the clock and the site's zone."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from helpers.common.date_time import time_range_delta
from schemas.reports import CalendarWindow, FixedWindow, ReportWindow, RollingWindow
from schemas.reports.api import MAX_WINDOW_DAYS

MAX_WINDOW = timedelta(days=MAX_WINDOW_DAYS)


def resolve_window(window: ReportWindow, now: datetime, site_timezone: ZoneInfo) -> tuple[datetime, datetime]:
    """(start, end) in UTC. A calendar period starts at local midnight in the site's zone, so a
    day across a DST change is 23 or 25 hours long; the current period (offset 0) ends now."""
    match window:
        case RollingWindow(duration=duration):
            return now - time_range_delta(duration), now
        case CalendarWindow():
            return _calendar_bounds(window, now, site_timezone)
        case FixedWindow(start_time=start_time, end_time=end_time):
            return start_time.astimezone(UTC), end_time.astimezone(UTC)
    raise ValueError(f"Unknown window kind: {window!r}")


def window_length_error(start: datetime, end: datetime) -> str | None:
    """Why a resolved window can't be reported on, or None if it can."""
    if end - start > MAX_WINDOW:
        return f"The report window is longer than {MAX_WINDOW_DAYS} days"
    return None


def _calendar_bounds(window: CalendarWindow, now: datetime, site_timezone: ZoneInfo) -> tuple[datetime, datetime]:
    today = now.astimezone(site_timezone).date()
    current_start = _period_start(window.period, today)
    start_day = _shift(window.period, current_start, window.offset)
    start = _local_midnight(start_day, site_timezone)
    if window.offset == 0:
        return start, now
    end = _local_midnight(_shift(window.period, current_start, window.offset + 1), site_timezone)
    return start, end


def _period_start(period: str, day: date) -> date:
    if period == "day":
        return day
    if period == "week":
        return day - timedelta(days=day.weekday())  # Monday
    return day.replace(day=1)


def _shift(period: str, period_start: date, periods: int) -> date:
    """The start of the period `periods` away from the one starting at `period_start`."""
    if period == "day":
        return period_start + timedelta(days=periods)
    if period == "week":
        return period_start + timedelta(weeks=periods)
    month_index = period_start.year * 12 + (period_start.month - 1) + periods
    return date(month_index // 12, month_index % 12 + 1, 1)


def _local_midnight(day: date, site_timezone: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=site_timezone).astimezone(UTC)
