"""
Unit tests for the schedule models (schemas.reports.schedules).

Guards what a cadence accepts: times as HH:MM, weekdays 0 to 6 once each (kept in order), days
of the month 1 to 28, hourly minutes 0 to 59; retention limits; and that an update can't null the
cadence or enabled.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from schemas.reports.schedules import (
    MonthlyCadence,
    ReportCadence,
    ReportScheduleCreateRequest,
    ReportScheduleUpdateRequest,
    WeeklyCadence,
)

CADENCE = TypeAdapter(ReportCadence)


class TestCadence:
    @pytest.mark.parametrize("time", ["6:00", "24:00", "06:60", "0600", ""])
    def test_time_is_hh_mm(self, time: str):
        with pytest.raises(ValidationError, match="time must be HH:MM"):
            CADENCE.validate_python({"kind": "daily", "time": time})

    def test_weekdays_are_kept_in_order(self):
        assert WeeklyCadence(kind="weekly", time="06:00", weekdays=[4, 0]).weekdays == [0, 4]

    @pytest.mark.parametrize("weekdays", [[], [7], [-1], [1, 1]])
    def test_bad_weekdays(self, weekdays: list[int]):
        with pytest.raises(ValidationError):
            WeeklyCadence(kind="weekly", time="06:00", weekdays=weekdays)

    @pytest.mark.parametrize("day", [0, 29, 31])
    def test_day_of_month_is_1_to_28(self, day: int):
        with pytest.raises(ValidationError):
            MonthlyCadence(kind="monthly", time="06:00", day_of_month=day)

    def test_kind_selects_the_model(self):
        assert CADENCE.validate_python({"kind": "hourly", "minute": 30}).kind == "hourly"
        with pytest.raises(ValidationError):
            CADENCE.validate_python({"kind": "hourly", "minute": 60})


class TestRequests:
    def test_retention_limits(self):
        with pytest.raises(ValidationError):
            ReportScheduleCreateRequest(template_id=1, cadence={"kind": "daily", "time": "06:00"}, keep_last=0)
        with pytest.raises(ValidationError):
            ReportScheduleCreateRequest(template_id=1, cadence={"kind": "daily", "time": "06:00"}, keep_days=3651)

    @pytest.mark.parametrize("field", ["enabled", "cadence"])
    def test_update_cannot_null_enabled_or_cadence(self, field: str):
        with pytest.raises(ValidationError, match="can't be null"):
            ReportScheduleUpdateRequest.model_validate({field: None})

    def test_update_can_clear_retention(self):
        update = ReportScheduleUpdateRequest.model_validate({"keep_last": None})
        assert "keep_last" in update.model_fields_set and update.keep_last is None
