"""
Unit tests for site_profiles.individual_sites.alpha_solar.calculations.

Guards the availability sample: only listed state codes count as online, null samples
count as not online, and no samples means "unknown" (None), not 0 %.
"""

from datetime import UTC, datetime, timedelta

from schemas.api_models import TimeseriesPoint
from site_profiles.individual_sites.alpha_solar.calculations import (
    availability_pct,
    count_online_samples,
)

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
