"""
Unit tests for reports.validation.

Guards the check that a report fits its site: every point and device must be on it, a site
function must be offered by its profile, device functions need a device of a type they apply to
(and site-wide ones refuse one), a KPI must name a numeric field, a chart only takes series
functions, and every error names its block.
"""

from reports.validation import definition_errors
from schemas.reports import (
    AlarmEventsTableBlock,
    ChartBlock,
    KpiBlock,
    PointSeries,
    PointStatKpi,
    PointStatsTableBlock,
    ReportDefinition,
    RollingWindow,
    SiteFunctionKpi,
    SiteFunctionSeries,
    TextBlock,
)
from unit.reports.report_fixtures import POWER, SOC, site_context


def definition(*blocks) -> ReportDefinition:
    return ReportDefinition(window=RollingWindow(kind="rolling", duration="1D"), blocks=list(blocks))


class TestValidDefinition:
    def test_fitting_definition_has_no_errors(self):
        report = definition(
            TextBlock(kind="text", id="intro", body="hello"),
            KpiBlock(kind="kpi", id="kpis", items=[
                PointStatKpi(source="point_stat", point_id=POWER.id, stat="max"),
                SiteFunctionKpi(source="site_function", function="site-energy-summary", field="energy_kwh"),
                SiteFunctionKpi(source="site_function", function="device-inverter-availability", device_id=2, field="availability_pct"),
            ]),
            ChartBlock(kind="chart", id="power", series=[PointSeries(source="point", point_id=POWER.id), SiteFunctionSeries(source="site_function", function="site-poi-power")]),
            PointStatsTableBlock(kind="point_stats_table", id="stats", point_ids=[POWER.id, SOC.id]),
            AlarmEventsTableBlock(kind="alarm_events_table", id="alarms", device_ids=[1]),
        )
        assert definition_errors(report, site_context()) == []


class TestPointsAndDevices:
    def test_unknown_points_are_named_with_their_block(self):
        report = definition(PointStatsTableBlock(kind="point_stats_table", id="stats", point_ids=[POWER.id, 999]), ChartBlock(kind="chart", id="chart", series=[PointSeries(source="point", point_id=998)]))
        assert definition_errors(report, site_context()) == [
            "stats: point 999 is not on this site",
            "chart: point 998 is not on this site",
        ]

    def test_unknown_alarm_table_device(self):
        report = definition(AlarmEventsTableBlock(kind="alarm_events_table", id="alarms", device_ids=[77]))
        assert definition_errors(report, site_context()) == ["alarms: device 77 is not on this site"]


class TestTextVariables:
    def test_variables_that_cannot_be_filled_in_are_named_with_their_block(self):
        report = definition(TextBlock(kind="text", id="intro", body="In the event {device_name} or {device:99.name} trips"))
        assert definition_errors(report, site_context()) == [
            "intro: unknown variable {device_name}",
            "intro: {device:99.name}: device 99 is not on this site",
        ]


class TestSiteFunctions:
    def test_function_the_site_does_not_offer(self):
        report = definition(KpiBlock(kind="kpi", id="kpis", items=[SiteFunctionKpi(source="site_function", function="site-nothing", field="x")]))
        assert definition_errors(report, site_context()) == ["kpis: site function 'site-nothing' is not offered by this site"]

    def test_device_function_needs_a_device(self):
        report = definition(KpiBlock(kind="kpi", id="kpis", items=[SiteFunctionKpi(source="site_function", function="device-inverter-availability", field="availability_pct")]))
        assert definition_errors(report, site_context()) == [
            "kpis: site function 'device-inverter-availability' is a device function: give a device_id"
        ]

    def test_device_function_on_a_device_type_it_does_not_apply_to(self):
        report = definition(KpiBlock(kind="kpi", id="kpis", items=[
            SiteFunctionKpi(source="site_function", function="device-inverter-availability", device_id=1, field="availability_pct"),
        ]))
        assert definition_errors(report, site_context()) == [
            "kpis: site function 'device-inverter-availability' does not apply to device 1 (BESS)"
        ]

    def test_site_function_refuses_a_device(self):
        report = definition(KpiBlock(kind="kpi", id="kpis", items=[SiteFunctionKpi(source="site_function", function="site-energy-summary", device_id=1, field="energy_kwh")]))
        assert definition_errors(report, site_context()) == ["kpis: site function 'site-energy-summary' is site-wide: remove device_id"]

    def test_kpi_field_must_be_numeric(self):
        report = definition(KpiBlock(kind="kpi", id="kpis", items=[SiteFunctionKpi(source="site_function", function="site-energy-summary", field="devices")]))
        assert definition_errors(report, site_context()) == [
            "kpis: site function 'site-energy-summary' has no numeric field 'devices' (available: energy_kwh)"
        ]

    def test_chart_needs_a_series_function(self):
        report = definition(ChartBlock(kind="chart", id="chart", series=[SiteFunctionSeries(source="site_function", function="site-energy-summary")]))
        assert definition_errors(report, site_context()) == [
            "chart: site function 'site-energy-summary' returns no series: use it in a kpi block"
        ]
