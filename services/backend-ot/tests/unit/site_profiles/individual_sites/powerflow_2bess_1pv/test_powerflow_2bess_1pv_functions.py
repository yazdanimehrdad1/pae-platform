"""
Unit tests for the Powerflow 2BESS 1PV site's functions.

Guards rolling_step: the rolling round trip efficiency's spacing follows the window, so every
range charts as a curve (1 min up to 1 hour, 15 min under a week, 1 hour for a week or more).
"""

from datetime import UTC, datetime, timedelta

import pytest

from schemas.site_profiles import TimeWindow
from site_profiles.individual_sites.powerflow_2bess_1pv.powerflow_2bess_1pv_functions import (
    rolling_step,
)

START = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("duration", "step"),
    [
        (timedelta(minutes=10), timedelta(minutes=1)),
        (timedelta(hours=1), timedelta(minutes=1)),
        (timedelta(hours=6), timedelta(minutes=15)),
        (timedelta(days=1), timedelta(minutes=15)),
        (timedelta(days=3), timedelta(minutes=15)),
        (timedelta(days=7), timedelta(hours=1)),
        (timedelta(days=90), timedelta(hours=1)),
    ],
)
def test_rolling_step_follows_the_window(duration, step):
    assert rolling_step(TimeWindow(start_time=START, end_time=START + duration)) == step
