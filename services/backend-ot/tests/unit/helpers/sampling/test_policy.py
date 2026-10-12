"""Unit tests for helpers.sampling.policy.

Invariant guarded: a chart gets every reading for any window up to 3 days (exactly 3 days
included) and plot values only for a longer window, decided by the window's length alone, and
nothing is sampled unless a chart asked (max_points) over a full window.
"""

from datetime import UTC, datetime, timedelta

from helpers.sampling.policy import RAW_WINDOW_MAX, use_plot_values

START = datetime(2026, 1, 15, tzinfo=UTC)


class TestUsePlotValues:
    def test_three_days_is_raw(self):
        assert RAW_WINDOW_MAX == timedelta(days=3)
        assert use_plot_values(START, START + timedelta(days=3), 2000) is False

    def test_one_second_past_three_days_takes_plot_values(self):
        assert use_plot_values(START, START + timedelta(days=3, seconds=1), 2000) is True

    def test_short_windows_are_raw(self):
        assert use_plot_values(START, START + timedelta(hours=1), 2000) is False

    def test_without_max_points_nothing_is_sampled(self):
        assert use_plot_values(START, START + timedelta(days=90), None) is False

    def test_without_a_full_window_nothing_is_sampled(self):
        assert use_plot_values(START, None, 2000) is False
        assert use_plot_values(None, START, 2000) is False
