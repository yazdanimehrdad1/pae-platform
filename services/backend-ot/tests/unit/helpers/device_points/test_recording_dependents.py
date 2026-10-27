"""Unit tests for which points a user alarm rule reads (helpers.device_points.recording_dependents).

Invariant guarded: alarm_rule_point_ids names every point a threshold or condition rule reads,
including compared-with points and points in nested groups, and none for a comms_stale rule. The
recording check (a point an alarm reads can't stop being recorded) and the alarm evaluator both use it.
"""

from helpers.device_points.recording_dependents import alarm_rule_point_ids
from schemas.api_models.alarms import CommsStaleAlarm, ConditionAlarm, ThresholdAlarm
from schemas.api_models.virtual_points import VirtualCondition, VirtualConditionGroup


class TestAlarmRulePointIds:
    def test_threshold_reads_its_point_and_the_compared_with_point(self):
        rule = ThresholdAlarm(
            kind="threshold",
            condition=VirtualCondition(point_id=7, operator=">", compare_point_id=8),
        )
        assert alarm_rule_point_ids(rule) == {7, 8}

    def test_condition_reads_every_point_in_nested_groups(self):
        rule = ConditionAlarm(
            kind="condition",
            when=VirtualConditionGroup(match="all", items=[
                VirtualCondition(point_id=1, operator=">=", value=20),
                VirtualConditionGroup(match="any", items=[
                    VirtualCondition(point_id=2, operator="bit_set", bit=1),
                    VirtualCondition(point_id=3, operator="==", value=1),
                ]),
            ]),
        )
        assert alarm_rule_point_ids(rule) == {1, 2, 3}

    def test_comms_stale_reads_no_points(self):
        assert alarm_rule_point_ids(CommsStaleAlarm(kind="comms_stale", device_id=4, stale_after_sec=60)) == set()
