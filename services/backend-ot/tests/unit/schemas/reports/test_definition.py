"""
Unit tests for the report models (schemas.reports).

Guards what a definition accepts: block ids are identifiers and unique within a report, a fixed
window has aware, ordered bounds, a calendar offset is never in the future, table statistics
don't repeat, unknown fields are refused, and a run request names exactly one of a template and
a definition.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas.reports import (
    CalendarWindow,
    FixedWindow,
    PointStatsTableBlock,
    ReportDefinition,
    RollingWindow,
    TextBlock,
)
from schemas.reports.api import ReportRunCreateRequest

START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2026, 10, 2, tzinfo=UTC)


def text(block_id: str) -> TextBlock:
    return TextBlock(kind="text", id=block_id, body="hello")


class TestBlockIds:
    @pytest.mark.parametrize("bad", ["", "1st", "Power", "has space", "a" * 41])
    def test_must_be_an_identifier(self, bad: str):
        with pytest.raises(ValidationError, match="id must start with a letter"):
            text(bad)

    def test_must_be_unique(self):
        with pytest.raises(ValidationError, match="block ids must be unique: intro"):
            ReportDefinition(window=RollingWindow(kind="rolling", duration="1D"), blocks=[text("intro"), text("intro")])


class TestWindows:
    def test_fixed_window_needs_an_offset(self):
        with pytest.raises(ValidationError, match="need a UTC offset"):
            FixedWindow(kind="fixed", start_time=datetime(2026, 10, 1), end_time=datetime(2026, 10, 2))

    def test_fixed_window_must_be_ordered(self):
        with pytest.raises(ValidationError, match="start_time must be before end_time"):
            FixedWindow(kind="fixed", start_time=END, end_time=START)

    def test_calendar_offset_is_never_in_the_future(self):
        with pytest.raises(ValidationError):
            CalendarWindow(kind="calendar", period="day", offset=1)

    def test_window_kind_selects_the_model(self):
        report = ReportDefinition.model_validate({
            "window": {"kind": "calendar", "period": "month"},
            "blocks": [{"kind": "text", "id": "intro", "body": "x"}],
        })
        assert report.window == CalendarWindow(kind="calendar", period="month", offset=-1)


class TestBlocks:
    def test_stats_must_not_repeat(self):
        with pytest.raises(ValidationError, match="stats must not repeat"):
            PointStatsTableBlock(kind="point_stats_table", id="stats", point_ids=[1], stats=["min", "min"])

    def test_default_stats(self):
        assert PointStatsTableBlock(kind="point_stats_table", id="stats", point_ids=[1]).stats == ["min", "max", "avg", "last"]

    def test_unknown_fields_are_refused(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            TextBlock.model_validate({"kind": "text", "id": "intro", "body": "x", "colour": "red"})

    def test_a_report_needs_a_block(self):
        with pytest.raises(ValidationError):
            ReportDefinition(window=RollingWindow(kind="rolling", duration="1D"), blocks=[])


class TestRunRequest:
    def test_template_or_definition(self):
        definition = ReportDefinition(window=RollingWindow(kind="rolling", duration="1D"), blocks=[text("intro")])
        assert ReportRunCreateRequest(template_id=1).template_id == 1
        assert ReportRunCreateRequest(definition=definition).definition == definition

    @pytest.mark.parametrize("both", [True, False])
    def test_not_both_and_not_neither(self, both: bool):
        definition = ReportDefinition(window=RollingWindow(kind="rolling", duration="1D"), blocks=[text("intro")])
        with pytest.raises(ValidationError, match="exactly one of template_id and definition"):
            ReportRunCreateRequest(template_id=1, definition=definition) if both else ReportRunCreateRequest()
