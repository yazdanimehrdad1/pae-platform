"""
Unit tests for reports.cadence.

Guards when a schedule next generates: on the site's clock (DST included), strictly after the
given time, on the chosen weekdays or day of month, and every hour at the chosen minute.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from reports.cadence import next_run_time
from schemas.reports.schedules import DailyCadence, HourlyCadence, MonthlyCadence, WeeklyCadence

PACIFIC = ZoneInfo("America/Los_Angeles")
# Tuesday 2026-10-13 13:00 in Los Angeles (PDT, UTC-7)
NOW = datetime(2026, 10, 13, 20, 0, tzinfo=UTC)


def pacific(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=PACIFIC).astimezone(UTC)


class TestNextRunTime:
    def test_daily_on_the_site_clock(self):
        assert next_run_time(DailyCadence(kind="daily", time="06:00"), PACIFIC, NOW) == pacific(2026, 10, 14, 6)
        assert next_run_time(DailyCadence(kind="daily", time="18:30"), PACIFIC, NOW) == pacific(2026, 10, 13, 18, 30)

    def test_strictly_after_the_given_time(self):
        due = pacific(2026, 10, 14, 6)
        assert next_run_time(DailyCadence(kind="daily", time="06:00"), PACIFIC, due) == pacific(2026, 10, 15, 6)

    def test_keeps_local_time_across_dst(self):
        # US DST ends 2026-11-01 02:00: 06:00 on Oct 31 is PDT (13:00 UTC), on Nov 1 PST (14:00 UTC)
        before_dst_ends = pacific(2026, 10, 30, 12)
        after = next_run_time(DailyCadence(kind="daily", time="06:00"), PACIFIC, before_dst_ends)
        later = next_run_time(DailyCadence(kind="daily", time="06:00"), PACIFIC, after)
        assert (after, later) == (datetime(2026, 10, 31, 13, 0, tzinfo=UTC), datetime(2026, 11, 1, 14, 0, tzinfo=UTC))

    def test_weekly_on_the_chosen_weekdays(self):
        cadence = WeeklyCadence(kind="weekly", time="07:00", weekdays=[0, 4])  # Monday and Friday
        assert next_run_time(cadence, PACIFIC, NOW) == pacific(2026, 10, 16, 7)
        assert next_run_time(cadence, PACIFIC, pacific(2026, 10, 16, 7)) == pacific(2026, 10, 19, 7)

    def test_monthly_on_the_chosen_day(self):
        cadence = MonthlyCadence(kind="monthly", time="05:00", day_of_month=1)
        assert next_run_time(cadence, PACIFIC, NOW) == pacific(2026, 11, 1, 5)

    def test_hourly_at_the_chosen_minute(self):
        assert next_run_time(HourlyCadence(kind="hourly", minute=15), PACIFIC, NOW) == datetime(2026, 10, 13, 20, 15, tzinfo=UTC)

    def test_utc_site(self):
        assert next_run_time(DailyCadence(kind="daily", time="06:00"), ZoneInfo("UTC"), NOW) == datetime(2026, 10, 14, 6, tzinfo=UTC)
