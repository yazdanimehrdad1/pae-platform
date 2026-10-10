"""
Unit tests for site_profiles.individual_sites.alpha_solar.alpha_solar_helper_functions (the calculations).

Guards the availability sample: only listed state codes count as online, null samples
count as not online, and no samples means "unknown" (None), not 0 %. And set_alarm_points: only
fresh, reported, non-zero readings mark their point as set.
"""

from datetime import UTC, datetime, timedelta

from schemas.api_models import TimeseriesPoint
from site_profiles.individual_sites.alpha_solar.alpha_solar_helper_functions import (
    availability_pct,
    count_online_samples,
    set_alarm_points,
)
from unit.site_fixtures import make_point, make_reading

START = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def states(values: list[float | None]) -> list[TimeseriesPoint]:
    return [
        TimeseriesPoint(time=START + timedelta(minutes=index), value=value)
        for index, value in enumerate(values)
    ]


class TestCountOnlineSamples:
    def test_counts_only_online_codes(self):
        assert count_online_samples(states([3.0, 4.0, 5.0, 6.0]), frozenset({3, 4})) == 2

    def test_null_is_not_online(self):
        assert count_online_samples(states([None, 3.0]), frozenset({3})) == 1


class TestAvailabilityPct:
    def test_share_in_percent(self):
        assert availability_pct(3, 4) == 75.0

    def test_no_samples_is_none(self):
        assert availability_pct(0, 0) is None


class TestSetAlarmPoints:
    OLDEST = START

    def reading(self, point_id: int, value: float | None, at: datetime):
        reading = make_reading(point_id, value)
        return reading.model_copy(update={"timestamp": at}) if reading.timestamp is not None else reading

    def test_fresh_non_zero_readings_mark_their_points_set(self):
        points = [make_point(1, 2, "a"), make_point(2, 2, "b"), make_point(3, 2, "c")]
        readings = [
            self.reading(1, 1.0, START),  # exactly at the limit counts
            self.reading(2, 0.0, START + timedelta(minutes=1)),
            self.reading(3, 7.0, START + timedelta(minutes=1)),
        ]
        assert [point.id for point in set_alarm_points(points, readings, self.OLDEST)] == [1, 3]

    def test_stale_never_reported_or_unread_points_are_not_set(self):
        points = [make_point(1, 2, "a"), make_point(2, 2, "b"), make_point(3, 2, "c")]
        readings = [
            self.reading(1, 1.0, START - timedelta(seconds=1)),
            self.reading(2, None, START),
            self.reading(9, 1.0, START),  # a reading of a point not asked about
        ]
        assert set_alarm_points(points, readings, self.OLDEST) == []
