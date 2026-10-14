"""
Unit tests for reports.windows.

Guards how a report window becomes UTC bounds: a rolling window ends now, a calendar period
starts at local midnight in the site's zone (so a DST day is 23 or 25 hours, a week starts on
Monday, months roll over years), the current period ends now, a fixed window is converted to
UTC, and windows over 92 days are refused.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from reports.windows import resolve_window, window_length_error
from schemas.reports import CalendarWindow, FixedWindow, RollingWindow

PACIFIC = ZoneInfo("America/Los_Angeles")
UTC_ZONE = ZoneInfo("UTC")
# Wednesday 2026-10-14 10:00 in Los Angeles (PDT, UTC-7)
NOW = datetime(2026, 10, 14, 17, 0, tzinfo=UTC)


def pacific(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=PACIFIC).astimezone(UTC)


class TestRollingWindow:
    def test_ends_now(self):
        assert resolve_window(RollingWindow(kind="rolling", duration="1D"), NOW, PACIFIC) == (NOW - timedelta(days=1), NOW)

    def test_month_is_30_days(self):
        start, end = resolve_window(RollingWindow(kind="rolling", duration="1M"), NOW, PACIFIC)
        assert end - start == timedelta(days=30)


class TestCalendarWindow:
    def test_previous_day_is_yesterday_in_site_time(self):
        window = CalendarWindow(kind="calendar", period="day", offset=-1)
        assert resolve_window(window, NOW, PACIFIC) == (pacific(2026, 10, 13), pacific(2026, 10, 14))

    def test_site_zone_decides_which_day_it_is(self):
        # 03:00 UTC on the 15th is still the 14th in Los Angeles
        late = datetime(2026, 10, 15, 3, 0, tzinfo=UTC)
        start, _ = resolve_window(CalendarWindow(kind="calendar", period="day", offset=-1), late, PACIFIC)
        assert start == pacific(2026, 10, 13)
        start_utc, _ = resolve_window(CalendarWindow(kind="calendar", period="day", offset=-1), late, UTC_ZONE)
        assert start_utc == datetime(2026, 10, 14, tzinfo=UTC)

    def test_dst_start_day_is_23_hours(self):
        # US DST began 2026-03-08: that local day lasts 23 hours
        after = datetime(2026, 3, 9, 20, 0, tzinfo=UTC)
        start, end = resolve_window(CalendarWindow(kind="calendar", period="day", offset=-1), after, PACIFIC)
        assert end - start == timedelta(hours=23)

    def test_dst_end_day_is_25_hours(self):
        # US DST ended 2026-11-01: that local day lasts 25 hours
        after = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)
        start, end = resolve_window(CalendarWindow(kind="calendar", period="day", offset=-1), after, PACIFIC)
        assert end - start == timedelta(hours=25)

    def test_previous_week_runs_monday_to_monday(self):
        start, end = resolve_window(CalendarWindow(kind="calendar", period="week", offset=-1), NOW, PACIFIC)
        assert (start, end) == (pacific(2026, 10, 5), pacific(2026, 10, 12))

    def test_previous_month(self):
        start, end = resolve_window(CalendarWindow(kind="calendar", period="month", offset=-1), NOW, PACIFIC)
        assert (start, end) == (pacific(2026, 9, 1), pacific(2026, 10, 1))

    def test_months_roll_over_the_year(self):
        january = datetime(2027, 1, 20, 12, tzinfo=UTC)
        start, end = resolve_window(CalendarWindow(kind="calendar", period="month", offset=-2), january, PACIFIC)
        assert (start, end) == (pacific(2026, 11, 1), pacific(2026, 12, 1))

    @pytest.mark.parametrize(
        ("period", "expected_start"),
        [("day", pacific(2026, 10, 14)), ("week", pacific(2026, 10, 12)), ("month", pacific(2026, 10, 1))],
    )
    def test_current_period_ends_now(self, period: str, expected_start: datetime):
        assert resolve_window(CalendarWindow(kind="calendar", period=period, offset=0), NOW, PACIFIC) == (expected_start, NOW)


class TestFixedWindow:
    def test_bounds_become_utc(self):
        window = FixedWindow(kind="fixed", start_time=pacific(2026, 9, 1), end_time=pacific(2026, 9, 2))
        start, end = resolve_window(window, NOW, PACIFIC)
        assert start.tzinfo == UTC and end.tzinfo == UTC
        assert end - start == timedelta(days=1)


class TestWindowLength:
    def test_92_days_is_allowed(self):
        assert window_length_error(NOW - timedelta(days=92), NOW) is None

    def test_longer_is_refused(self):
        assert window_length_error(NOW - timedelta(days=92, seconds=1), NOW) == "The report window is longer than 92 days"
