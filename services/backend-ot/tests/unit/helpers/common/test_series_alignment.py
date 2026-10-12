"""Unit tests for helpers.common.series_alignment (lining up series from several points).

Invariant guarded: series are lined up at their own sample times, never a resampled grid. One poll
cycle across devices (within ALIGN_TOLERANCE) is one aligned time, each series carries its last
value forward for at most `max_gap`, and a series with nothing recent enough is None, not a
made-up value.
"""

from datetime import UTC, datetime, timedelta

from helpers.common.series_alignment import ALIGN_TOLERANCE, align_series, aligned_times
from schemas.internal_models import TimestampedValue

T0 = datetime(2026, 9, 28, 10, 0, 0, tzinfo=UTC)
GAP = timedelta(seconds=30)


def at(seconds: float, value: float) -> TimestampedValue:
    return TimestampedValue(time=T0 + timedelta(seconds=seconds), value=value)


def offsets(times: list[datetime]) -> list[float]:
    return [(time - T0).total_seconds() for time in times]


class TestAlignedTimes:
    def test_one_poll_cycle_across_devices_is_one_time_at_its_last_sample(self):
        series = {1: [at(0, 1), at(10, 1)], 2: [at(0.3, 1), at(10.3, 1)]}
        assert offsets(aligned_times(series)) == [0.3, 10.3]

    def test_times_further_apart_than_the_tolerance_stay_separate(self):
        apart = ALIGN_TOLERANCE.total_seconds() + 0.5
        assert offsets(aligned_times({1: [at(0, 1)], 2: [at(apart, 1)]})) == [0.0, apart]

    def test_each_series_keeps_its_own_rate(self):
        # a 10 s series and a 30 s series: every sample time of either appears once
        series = {1: [at(seconds, 1) for seconds in (0, 10, 20, 30)], 2: [at(0, 1), at(30, 1)]}
        assert offsets(aligned_times(series)) == [0.0, 10.0, 20.0, 30.0]


class TestAlignSeries:
    def test_values_carry_forward_between_a_series_samples(self):
        series = {1: [at(0, 1), at(10, 2), at(20, 3)], 2: [at(0, 10), at(20, 30)]}
        aligned = align_series(series, GAP)
        assert [(offsets([row.time])[0], row.values) for row in aligned] == [
            (0.0, {1: 1, 2: 10}),
            (10.0, {1: 2, 2: 10}),
            (20.0, {1: 3, 2: 30}),
        ]

    def test_a_value_older_than_max_gap_is_none(self):
        series = {1: [at(0, 1), at(60, 2)], 2: [at(0, 10)]}
        assert align_series(series, GAP)[-1].values == {1: 2, 2: None}

    def test_a_series_that_has_not_started_yet_is_none(self):
        series = {1: [at(0, 1), at(10, 2)], 2: [at(10, 20)]}
        assert [row.values for row in align_series(series, GAP)] == [{1: 1, 2: None}, {1: 2, 2: 20}]

    def test_samples_in_any_order(self):
        assert [row.values for row in align_series({1: [at(10, 2), at(0, 1)]}, GAP)] == [{1: 1}, {1: 2}]

    def test_no_samples_gives_nothing(self):
        assert align_series({1: []}, GAP) == []
