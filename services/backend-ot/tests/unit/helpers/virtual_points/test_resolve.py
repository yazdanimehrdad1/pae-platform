"""Unit tests for helpers.virtual_points.resolve (computing virtual points on read).

Invariant guarded: a virtual point's values come only from its inputs' stored readings. Inputs from
different devices are lined up by carrying each one's last value forward for at most `max_gap`; one
poll cycle across devices yields one sample; a missing or stale input yields no value rather than a
made-up one.
"""

from datetime import UTC, datetime, timedelta

from helpers.virtual_points.resolve import evaluate_latest, evaluate_series
from schemas.api_models import (
    VirtualCalculationDefinition,
    VirtualCase,
    VirtualCondition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
)
from schemas.internal_models import TimestampedValue

T0 = datetime(2026, 9, 28, 10, 0, 0, tzinfo=UTC)
GAP = timedelta(seconds=30)
SUM_1_2 = VirtualCalculationDefinition(kind="calculation", function="sum", inputs=[1, 2])


def at(seconds: float, value: float) -> TimestampedValue:
    return TimestampedValue(time=T0 + timedelta(seconds=seconds), value=value)


def values(samples: list[TimestampedValue]) -> list[tuple[float, float]]:
    return [((sample.time - T0).total_seconds(), sample.value) for sample in samples]


class TestEvaluateSeries:
    def test_one_sample_per_poll_cycle_across_devices(self):
        # Device 2 is polled 0.3 s after device 1 in each 10 s cycle.
        inputs = {1: [at(0, 1), at(10, 2)], 2: [at(0.3, 10), at(10.3, 20)]}
        assert values(evaluate_series(SUM_1_2, inputs, GAP)) == [(0.3, 11.0), (10.3, 22.0)]

    def test_an_input_carries_its_last_value_forward(self):
        # Input 2 is read less often: its last value is reused while it's within max_gap.
        inputs = {1: [at(0, 1), at(10, 2), at(20, 3)], 2: [at(0, 100)]}
        assert values(evaluate_series(SUM_1_2, inputs, GAP)) == [(0, 101.0), (10, 102.0), (20, 103.0)]

    def test_an_input_older_than_max_gap_gives_no_value(self):
        inputs = {1: [at(0, 1), at(40, 2)], 2: [at(0, 100)]}
        assert values(evaluate_series(SUM_1_2, inputs, GAP)) == [(0, 101.0)]

    def test_times_before_every_input_has_a_value_are_skipped(self):
        inputs = {1: [at(0, 1), at(10, 2)], 2: [at(10, 100)]}
        assert values(evaluate_series(SUM_1_2, inputs, GAP)) == [(10, 102.0)]

    def test_a_missing_input_gives_nothing(self):
        assert evaluate_series(SUM_1_2, {1: [at(0, 1)]}, GAP) == []

    def test_unsorted_input_is_handled(self):
        inputs = {1: [at(10, 2), at(0, 1)], 2: [at(10, 20), at(0, 10)]}
        assert values(evaluate_series(SUM_1_2, inputs, GAP)) == [(0, 11.0), (10, 22.0)]

    def test_a_condition_over_time(self):
        definition = VirtualConditionDefinition(
            kind="condition",
            cases=[VirtualCase(output=1, when=VirtualConditionGroup(match="all", items=[
                VirtualCondition(point_id=1, operator=">=", value=20),
                VirtualCondition(point_id=2, operator="bit_set", bit=1),
            ]))],
            default_output=0,
        )
        inputs = {1: [at(0, 50), at(10, 10), at(20, 60)], 2: [at(0, 0b10), at(10, 0b10), at(20, 0b00)]}
        assert values(evaluate_series(definition, inputs, GAP)) == [(0, 1.0), (10, 0.0), (20, 0.0)]


class TestEvaluateLatest:
    def test_value_at_the_newest_input_time(self):
        latest = {1: at(9.7, 1), 2: at(10, 2)}
        assert evaluate_latest(SUM_1_2, latest, GAP) == at(10, 3)

    def test_a_stale_or_missing_input_gives_none(self):
        assert evaluate_latest(SUM_1_2, {1: at(0, 1), 2: at(40, 2)}, GAP) is None
        assert evaluate_latest(SUM_1_2, {1: at(0, 1), 2: None}, GAP) is None
        assert evaluate_latest(SUM_1_2, {1: at(0, 1)}, GAP) is None
