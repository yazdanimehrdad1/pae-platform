"""
Unit tests for reports.stats.

Guards the Python point statistics used for virtual points: min/max/avg/first/last/count of the
samples in time order whatever order they come in, and buckets at the site's local hour and
midnight (not UTC), oldest first, with no entry for a point without samples.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from reports.stats import bucket_start, compute_point_stats

PACIFIC = ZoneInfo("America/Los_Angeles")
BASE = datetime(2026, 10, 14, 6, 30, tzinfo=UTC)  # 23:30 on the 13th in Los Angeles


class TestComputePointStats:
    def test_whole_window_stats_in_time_order(self):
        samples = [(BASE + timedelta(minutes=2), 30.0), (BASE, 10.0), (BASE + timedelta(minutes=1), 20.0)]
        (entry,) = compute_point_stats(7, samples, "none", PACIFIC)
        assert entry.point_id == 7
        assert entry.bucket_start is None
        assert entry.values == {"min": 10.0, "max": 30.0, "avg": 20.0, "first": 10.0, "last": 30.0, "count": 3.0}

    def test_no_samples_gives_no_entry(self):
        assert compute_point_stats(7, [], "none", PACIFIC) == []

    def test_day_buckets_split_at_local_midnight(self):
        before_midnight = BASE  # 23:30 local on the 13th
        after_midnight = BASE + timedelta(hours=1)  # 00:30 local on the 14th
        entries = compute_point_stats(7, [(after_midnight, 2.0), (before_midnight, 1.0)], "day", PACIFIC)
        assert [entry.bucket_start for entry in entries] == [
            datetime(2026, 10, 13, tzinfo=PACIFIC).astimezone(UTC),
            datetime(2026, 10, 14, tzinfo=PACIFIC).astimezone(UTC),
        ]
        assert [entry.values["count"] for entry in entries] == [1.0, 1.0]

    def test_hour_buckets(self):
        samples = [(BASE, 1.0), (BASE + timedelta(minutes=20), 3.0), (BASE + timedelta(minutes=40), 5.0)]
        entries = compute_point_stats(7, samples, "hour", PACIFIC)
        assert [(entry.bucket_start, entry.values["avg"]) for entry in entries] == [
            (datetime(2026, 10, 14, 6, 0, tzinfo=UTC), 2.0),
            (datetime(2026, 10, 14, 7, 0, tzinfo=UTC), 5.0),
        ]


class TestBucketStart:
    def test_none_bucket_has_no_start(self):
        assert bucket_start(BASE, "none", PACIFIC) is None

    def test_repeated_fall_back_hour_keeps_its_instant(self):
        # 2026-11-01 01:30 happens twice in Los Angeles; each gets its own hour bucket
        first = datetime(2026, 11, 1, 8, 30, tzinfo=UTC)  # 01:30 PDT
        second = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)  # 01:30 PST
        assert bucket_start(first, "hour", PACIFIC) == datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        assert bucket_start(second, "hour", PACIFIC) == datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
