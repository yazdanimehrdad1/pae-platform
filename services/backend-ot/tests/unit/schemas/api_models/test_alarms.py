"""
Unit tests for schemas.api_models.alarms.

Guards the alarm rule shapes the API accepts (422 otherwise): a threshold is one virtual-point
comparison (value, another point, or a bit test without deadband), a condition is a group nested
at most two levels, comms-stale needs a positive timeout; names are identifiers; an update body
rejects unknown fields; and the typed column round-trips a rule.
"""

import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.dialects import postgresql

from schemas.api_models.alarms import (
    AlarmDefinitionCreateRequest,
    AlarmDefinitionUpdateRequest,
    AlarmRule,
    ConditionAlarm,
    ThresholdAlarm,
)
from schemas.db_models.column_types import AlarmRuleJSON

RULE = TypeAdapter(AlarmRule)


def threshold(**condition: object) -> dict[str, object]:
    return {"kind": "threshold", "condition": {"point_id": 1, "operator": ">", "value": 5} | condition}


class TestRules:
    def test_threshold_against_a_value_or_another_point(self):
        assert isinstance(RULE.validate_python(threshold()), ThresholdAlarm)
        against_point = RULE.validate_python(threshold(value=None, compare_point_id=2) | {"deadband": 1})
        assert against_point.condition.compare_point_id == 2

    def test_bit_test_takes_no_deadband(self):
        bit = threshold(operator="bit_set", value=None, bit=3)
        RULE.validate_python(bit)
        with pytest.raises(ValidationError, match="takes no deadband"):
            RULE.validate_python(bit | {"deadband": 1})

    def test_comparison_needs_exactly_one_operand(self):
        with pytest.raises(ValidationError):
            RULE.validate_python(threshold(value=None))

    def test_condition_group_nests_two_levels_at_most(self):
        leaf = {"point_id": 1, "operator": ">", "value": 5}
        two = {"kind": "condition", "when": {"match": "all", "items": [leaf, {"match": "any", "items": [leaf]}]}}
        assert isinstance(RULE.validate_python(two), ConditionAlarm)
        three = {"kind": "condition", "when": {"match": "all", "items": [{"match": "any", "items": [{"match": "all", "items": [leaf]}]}]}}
        with pytest.raises(ValidationError, match="nest at most"):
            RULE.validate_python(three)

    def test_comms_stale_needs_a_positive_timeout(self):
        with pytest.raises(ValidationError):
            RULE.validate_python({"kind": "comms_stale", "device_id": 1, "stale_after_sec": 0})


class TestBodies:
    @pytest.mark.parametrize("name", ["1_bad", "has space", "", "x" * 151])
    def test_name_is_an_identifier(self, name: str):
        with pytest.raises(ValidationError):
            AlarmDefinitionCreateRequest.model_validate({"name": name, "severity": "fault", "rule": threshold()})

    def test_defaults(self):
        request = AlarmDefinitionCreateRequest.model_validate({"name": "ok", "severity": "warning", "rule": threshold()})
        assert (request.enabled, request.notify_mobile, request.notify_email, request.message) == (True, False, False, "")
        assert "shown" not in AlarmDefinitionCreateRequest.model_fields  # enabled = evaluated and shown

    def test_update_rejects_unknown_fields(self):
        with pytest.raises(ValidationError):
            AlarmDefinitionUpdateRequest.model_validate({"kind": "condition"})


class TestRuleColumn:
    def test_round_trip(self):
        column, dialect = AlarmRuleJSON(), postgresql.dialect()
        rule = RULE.validate_python(threshold(value=None, compare_point_id=2))
        assert column.process_result_value(column.process_bind_param(rule, dialect), dialect) == rule
        assert column.process_result_value({"kind": "nonsense"}, dialect) is None
