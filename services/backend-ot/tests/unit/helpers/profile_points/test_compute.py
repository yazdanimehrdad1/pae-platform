"""
Unit tests for helpers.profile_points.compute: the window a run computes and the values it keeps.

Guards that a run never recomputes what is stored (start is exclusive), never computes a poll that
may not be fully stored yet (settle), catches a long gap up in capped chunks, starts a new point
`backfill` back, and keeps one value per timestamp inside the window.
"""

from datetime import UTC, datetime, timedelta

from helpers.profile_points.compute import compute_window, values_in_window
from schemas.internal_models import TimestampedValue

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
SETTLE = timedelta(seconds=10)
MAX_WINDOW = timedelta(hours=1)
NONE = timedelta(0)


def at(seconds: int, value: float = 1.0) -> TimestampedValue:
    return TimestampedValue(time=NOW + timedelta(seconds=seconds), value=value)


class TestComputeWindow:
    def test_continues_after_the_last_computed_up_to_the_settled_poll(self):
        last = NOW - timedelta(seconds=30)
        assert compute_window(last, NOW, NONE, SETTLE, MAX_WINDOW) == (last, NOW - SETTLE)

    def test_nothing_to_do_when_already_at_the_settled_poll(self):
        assert compute_window(NOW - SETTLE, NOW, NONE, SETTLE, MAX_WINDOW) is None
        assert compute_window(NOW, NOW, NONE, SETTLE, MAX_WINDOW) is None

    def test_first_run_without_backfill_starts_from_now(self):
        assert compute_window(None, NOW, NONE, SETTLE, MAX_WINDOW) is None

    def test_first_run_with_backfill_reaches_back(self):
        backfill = timedelta(minutes=30)
        assert compute_window(None, NOW, backfill, SETTLE, MAX_WINDOW) == (NOW - SETTLE - backfill, NOW - SETTLE)

    def test_a_long_gap_is_caught_up_in_capped_chunks(self):
        last = NOW - timedelta(hours=3)
        first = compute_window(last, NOW, NONE, SETTLE, MAX_WINDOW)
        assert first == (last, last + MAX_WINDOW)
        assert first is not None
        second = compute_window(first[1], NOW, NONE, SETTLE, MAX_WINDOW)
        assert second == (last + MAX_WINDOW, last + 2 * MAX_WINDOW)


class TestValuesInWindow:
    def test_start_is_exclusive_and_end_inclusive(self):
        start, end = NOW, NOW + timedelta(seconds=20)
        kept = values_in_window([at(-10), at(0), at(10), at(20), at(30)], start, end)
        assert [value.time for value in kept] == [NOW + timedelta(seconds=10), end]

    def test_one_value_per_timestamp_last_wins_and_sorted(self):
        kept = values_in_window([at(20, 2.0), at(10, 1.0), at(20, 3.0)], NOW, NOW + timedelta(seconds=30))
        assert [(value.time, value.value) for value in kept] == [
            (NOW + timedelta(seconds=10), 1.0),
            (NOW + timedelta(seconds=20), 3.0),
        ]

    def test_empty_is_empty(self):
        assert values_in_window([], NOW, NOW + timedelta(seconds=10)) == []
