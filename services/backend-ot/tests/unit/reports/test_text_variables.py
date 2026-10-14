"""
Unit tests for reports.text_variables.

Guards the variables of a text block: site variables, device fields and point fields (names,
units, statistics over the window) fill in from the site and the window's statistics; a statistic
without readings is a dash and a count a whole number; every variable that can't be filled in on
the site is reported (typos, ids not on it, unknown fields); and numbers read like the tables.
"""

from datetime import UTC, datetime

import pytest

from reports.text_variables import (
    format_number,
    render_text,
    stat_point_ids,
    text_variable_catalog,
    text_variable_errors,
)
from schemas.reports.internal import PointStatValues
from unit.reports.report_fixtures import POWER, SOC, WINDOW_END, WINDOW_START, site_context


def local(time: datetime) -> str:
    return time.astimezone(UTC).strftime("%Y-%m-%d %H:%M")


def render(body: str, stats: list[PointStatValues] | None = None) -> str:
    return render_text(body, site_context(), WINDOW_START, WINDOW_END, "UTC", local, stats or [])


class TestRender:
    def test_site_variables(self):
        assert render("{site_name} ({site_id}, {site_location}) from {window_start} to {window_end} {timezone}") == (
            "Site (1001, Fresno, CA) from 2026-10-13 07:00 to 2026-10-14 07:00 UTC"
        )

    def test_device_fields(self):
        assert render("In the event {device:1.name} ({device:1.type}) trips") == "In the event device_1 (BESS) trips"

    def test_point_fields_and_statistics(self):
        stats = [PointStatValues(point_id=POWER.id, values={"max": 1234.5678, "avg": 12.3456, "count": 42.0})]
        body = "{point:11.name} on {point:11.device} peaked at {point:11.max} {point:11.unit}, avg {point:11.avg}, {point:11.count} readings"
        assert render(body, stats) == "active_power on device_1 peaked at 1,235 kW, avg 12.35, 42 readings"

    def test_statistics_without_readings(self):
        assert render("{point:12.last} {point:12.unit}, {point:12.count} readings") == "— %, 0 readings"

    def test_unknown_variables_are_left_as_written(self):
        assert render("{device_name} and {device:99.name} and {braces}") == "{device_name} and {device:99.name} and {braces}"


class TestErrors:
    def test_a_fitting_body_has_none(self):
        assert text_variable_errors("{site_name}: {device:2.name} {point:12.max} {point:21.device}", site_context()) == []

    @pytest.mark.parametrize(("body", "error"), [
        ("{device_name}", "unknown variable {device_name}"),
        ("{sitename}", "unknown variable {sitename}"),
        ("{device:99.name}", "{device:99.name}: device 99 is not on this site"),
        ("{device:1.colour}", "{device:1.colour}: a device has no 'colour' (use name, type, vendor, model)"),
        ("{point:99.max}", "{point:99.max}: point 99 is not on this site"),
        ("{point:11.median}", "{point:11.median}: a point has no 'median' (use name, unit, device, min, max, avg, first, last, count)"),
        ("{sensor:11.name}", "unknown variable {sensor:11.name}"),
    ])
    def test_reports_what_cannot_be_filled_in(self, body: str, error: str):
        assert text_variable_errors(body, site_context()) == [error]

    def test_plain_text_and_other_braces_are_fine(self):
        assert text_variable_errors("No variables, {not a variable}, {UPPER}", site_context()) == []


class TestStatPointIds:
    def test_only_points_whose_statistics_are_shown(self):
        assert stat_point_ids("{point:12.max} {point:11.name} {point:11.avg} {point:12.last} {point:21.name}") == [POWER.id, SOC.id]


class TestFormatNumber:
    @pytest.mark.parametrize(("value", "text"), [(1234.567, "1,235"), (12.3456, "12.35"), (12.5, "12.5"), (0.12345, "0.123"), (100.0, "100"), (-7.0, "-7")])
    def test_fewer_decimals_for_bigger_numbers(self, value: float, text: str):
        assert format_number(value) == text


class TestCatalog:
    def test_lists_every_variable_with_a_description(self):
        catalog = text_variable_catalog()
        assert [variable.name for variable in catalog.site][:2] == ["site_name", "site_id"]
        assert [variable.name for variable in catalog.device_fields] == ["name", "type", "vendor", "model"]
        assert "max" in [variable.name for variable in catalog.point_fields]
        assert all(variable.description for variable in catalog.site + catalog.device_fields + catalog.point_fields)
