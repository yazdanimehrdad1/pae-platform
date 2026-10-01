"""
Unit tests for helpers.alarms.engine (one evaluation of one alarm).

Guards the same semantics as the UI's reference engine (web-plusdas ruleEngine.ts):
- a raise waits for `delay` of continuous violation, then happens at the evaluation completing it;
- a threshold clears only past the limit by `deadband` (value or another point); `==`/`!=`, bit
  tests and conditions clear as soon as they no longer hold;
- missing data changes nothing but resets the delay timer;
- comms-stale raises back-dated to last success + timeout and clears on a fresh poll;
- a disabled alarm clears an active one.
"""

from datetime import UTC, datetime, timedelta

from helpers.alarms.engine import (
    AlarmObservation,
    AlarmState,
    disabled_step,
    observe_comms_stale,
    observe_condition,
    observe_threshold,
    step,
    threshold_cleared,
)
from schemas.api_models import VirtualCondition, VirtualConditionGroup
from schemas.api_models.alarms import CommsStaleAlarm, ConditionAlarm, ThresholdAlarm

T0 = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
NO_DELAY = timedelta(0)


def at(seconds: int) -> datetime:
    return T0 + timedelta(seconds=seconds)


def holding(value: float = 1.0) -> AlarmObservation:
    return AlarmObservation(holds=True, cleared=False, value=value, device_id=7)


def normal() -> AlarmObservation:
    return AlarmObservation(holds=False, cleared=True)


def threshold(operator: str, deadband: float = 0.0, **condition: object) -> ThresholdAlarm:
    return ThresholdAlarm(kind="threshold", deadband=deadband,
                          condition=VirtualCondition.model_validate({"point_id": 1, "operator": operator, "value": 10} | condition))


class TestStep:
    def test_no_delay_raises_at_once_with_value_and_device(self):
        state, transition = step(AlarmState(), holding(42), NO_DELAY, at(0))
        assert state.active and transition is not None
        assert (transition.kind, transition.at, transition.value, transition.device_id) == ("raise", at(0), 42, 7)

    def test_delay_needs_continuous_violation(self):
        delay = timedelta(seconds=30)
        state, transition = step(AlarmState(), holding(), delay, at(0))
        assert (state.condition_since, transition) == (at(0), None)
        state, transition = step(state, holding(), delay, at(20))
        assert transition is None
        state, transition = step(state, holding(), delay, at(30))
        assert transition is not None and transition.at == at(30) and state.active

    def test_a_break_in_the_violation_restarts_the_delay(self):
        delay = timedelta(seconds=30)
        state, _ = step(AlarmState(), holding(), delay, at(0))
        state, _ = step(state, normal(), delay, at(10))
        assert state.condition_since is None
        state, transition = step(state, holding(), delay, at(20))
        assert transition is None and state.condition_since == at(20)

    def test_missing_data_changes_nothing_but_resets_the_timer(self):
        state, transition = step(AlarmState(condition_since=at(0)), None, timedelta(seconds=30), at(10))
        assert (state, transition) == (AlarmState(), None)
        active = AlarmState(active=True)
        assert step(active, None, NO_DELAY, at(10)) == (active, None)

    def test_active_alarm_clears_only_when_the_clear_test_passes(self):
        active = AlarmState(active=True)
        still_bad = AlarmObservation(holds=False, cleared=False)  # inside the deadband
        assert step(active, still_bad, NO_DELAY, at(5)) == (active, None)
        state, transition = step(active, normal(), NO_DELAY, at(10))
        assert not state.active and transition is not None and (transition.kind, transition.at) == ("clear", at(10))

    def test_raise_can_be_back_dated(self):
        observation = holding().model_copy(update={"raise_at": at(-60)})
        _, transition = step(AlarmState(), observation, NO_DELAY, at(0))
        assert transition is not None and transition.at == at(-60)

    def test_disabled_clears_an_active_alarm_only(self):
        assert disabled_step(AlarmState(active=True), at(0))[1] is not None
        assert disabled_step(AlarmState(), at(0)) == (AlarmState(), None)


class TestThresholdClear:
    def test_above_clears_below_limit_minus_deadband(self):
        rule = threshold(">", deadband=2)
        assert not threshold_cleared(rule.condition, {1: 9}, rule.deadband)
        assert threshold_cleared(rule.condition, {1: 7.9}, rule.deadband)

    def test_below_clears_above_limit_plus_deadband(self):
        rule = threshold("<=", deadband=2)
        assert not threshold_cleared(rule.condition, {1: 11.5}, rule.deadband)
        assert threshold_cleared(rule.condition, {1: 12.1}, rule.deadband)

    def test_against_another_point_uses_its_value_as_the_limit(self):
        rule = threshold(">", deadband=5, value=None, compare_point_id=2)
        assert not threshold_cleared(rule.condition, {1: 98, 2: 100}, rule.deadband)
        assert threshold_cleared(rule.condition, {1: 94, 2: 100}, rule.deadband)

    def test_equality_and_bit_tests_clear_when_false(self):
        equal = threshold("==")
        assert threshold_cleared(equal.condition, {1: 9}, 0) and not threshold_cleared(equal.condition, {1: 10}, 0)
        bit = threshold("bit_set", value=None, bit=1)
        assert threshold_cleared(bit.condition, {1: 0b01}, 0) and not threshold_cleared(bit.condition, {1: 0b10}, 0)


class TestObservations:
    def test_threshold_observation_carries_value_and_the_points_device(self):
        observation = observe_threshold(threshold(">"), {1: 12}, {1: 7})
        assert observation is not None and (observation.holds, observation.cleared, observation.value, observation.device_id) == (True, False, 12, 7)

    def test_threshold_or_condition_with_a_missing_input_is_no_data(self):
        assert observe_threshold(threshold(">", value=None, compare_point_id=2), {1: 12, 2: None}, {}) is None
        rule = ConditionAlarm(kind="condition", when=VirtualConditionGroup(match="all", items=[
            VirtualCondition(point_id=1, operator=">", value=0), VirtualCondition(point_id=2, operator=">", value=0),
        ]))
        assert observe_condition(rule, {1: 1}, {}) is None

    def test_condition_device_is_set_only_when_all_points_share_one(self):
        rule = ConditionAlarm(kind="condition", when=VirtualConditionGroup(match="any", items=[
            VirtualCondition(point_id=1, operator=">", value=0), VirtualCondition(point_id=2, operator=">", value=0),
        ]))
        same = observe_condition(rule, {1: 1, 2: 0}, {1: 7, 2: 7})
        mixed = observe_condition(rule, {1: 0, 2: 0}, {1: 7, 2: 8})
        assert same is not None and (same.holds, same.device_id) == (True, 7)
        assert mixed is not None and (mixed.holds, mixed.cleared, mixed.device_id) == (False, True, None)

    def test_comms_stale_back_dates_and_needs_a_first_success(self):
        rule = CommsStaleAlarm(kind="comms_stale", device_id=3, stale_after_sec=60)
        stale = observe_comms_stale(rule, at(0), at(90))
        fresh = observe_comms_stale(rule, at(50), at(90))
        assert stale is not None and stale.holds and stale.raise_at == at(60) and stale.device_id == 3
        assert fresh is not None and not fresh.holds and fresh.cleared
        assert observe_comms_stale(rule, None, at(90)) is None
