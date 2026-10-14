"""
Unit tests for the block resolvers (reports.blocks), against an in-memory data source.

Guards what each block kind stores: text with the site and window filled in (in site time); KPI
values from point statistics and site functions, one failing function not failing the others;
charts in the block's order with an empty series for a point without readings; statistics tables
by point then bucket with a placeholder row for a point without readings; alarm tables filtered,
limited and counted; and a failing block stored as an error of its own kind.
"""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel

from reports.blocks import resolve_block
from schemas.api_models import PointTimeseries, TimeseriesPoint
from schemas.api_models.alarms import AlarmEventResponse
from schemas.reports import (
    AlarmEventsTableBlock,
    AlarmEventsTableResult,
    ChartBlock,
    ChartResult,
    KpiBlock,
    KpiResult,
    PointSeries,
    PointStatKpi,
    PointStatsTableBlock,
    PointStatsTableResult,
    SiteFunctionKpi,
    SiteFunctionSeries,
    TextBlock,
    TextResult,
)
from schemas.reports.internal import PointStatValues
from unit.reports.fake_data_source import FakeReportDataSource
from unit.reports.report_fixtures import POWER, SOC, WINDOW_END, WINDOW_START, block_context
from utils.exceptions import NotFoundError


class EnergySummary(BaseModel):
    energy_kwh: float


class PoiPower(BaseModel):
    peak_kw: float
    series: PointTimeseries


def series(point_id: int, name: str, values: list[float]) -> PointTimeseries:
    return PointTimeseries(
        id=point_id, name=name, data_type="float32",
        timeseries=[TimeseriesPoint(time=WINDOW_START + timedelta(minutes=index), value=value) for index, value in enumerate(values)],
    )


def event(event_id: int, device_id: int | None, raised_at: datetime, cleared_at: datetime | None, severity: str = "fault") -> AlarmEventResponse:
    return AlarmEventResponse(
        id=event_id, definition_id=5, site_id=1001, device_id=device_id, severity=severity,
        raised_at=raised_at, cleared_at=cleared_at, message="tripped",
    )


class TestText:
    async def test_fills_in_site_and_window_in_site_time(self):
        block = TextBlock(kind="text", id="intro", body="{site_name} from {window_start} to {window_end} ({timezone})")
        result = await resolve_block(block, block_context(FakeReportDataSource()))
        assert isinstance(result, TextResult)
        assert result.body == "Site from 2026-10-13 00:00 to 2026-10-14 00:00 (America/Los_Angeles)"


class TestTextVariables:
    async def test_reads_the_statistics_the_text_shows(self):
        data_source = FakeReportDataSource(stats=[PointStatValues(point_id=POWER.id, values={"max": 42.0})])
        block = TextBlock(kind="text", id="intro", body="If {device:1.name} trips, {point:11.name} peaked at {point:11.max} {point:11.unit}")
        result = await resolve_block(block, block_context(data_source))
        assert isinstance(result, TextResult)
        assert result.body == "If device_1 trips, active_power peaked at 42 kW"
        assert data_source.stats_calls == [([POWER.id], "none")]

    async def test_reads_no_statistics_when_none_are_shown(self):
        data_source = FakeReportDataSource()
        await resolve_block(TextBlock(kind="text", id="intro", body="{device:1.name}"), block_context(data_source))
        assert data_source.stats_calls == []


class TestKpi:
    async def test_point_stats_and_function_fields(self):
        data_source = FakeReportDataSource(
            stats=[PointStatValues(point_id=POWER.id, values={"max": 42.0, "count": 10.0})],
            function_results={"site-energy-summary": EnergySummary(energy_kwh=12.5)},
        )
        block = KpiBlock(kind="kpi", id="kpis", items=[
            PointStatKpi(source="point_stat", point_id=POWER.id, stat="max"),
            PointStatKpi(source="point_stat", point_id=SOC.id, stat="count", label="SOC samples"),
            SiteFunctionKpi(source="site_function", function="site-energy-summary", field="energy_kwh", label="Energy"),
        ])
        result = await resolve_block(block, block_context(data_source))
        assert isinstance(result, KpiResult)
        assert [(item.label, item.value, item.unit) for item in result.items] == [
            ("active_power max", 42.0, "kW"),
            ("SOC samples", 0.0, None),  # no readings: a count of zero, not missing
            ("Energy", 12.5, "kWh"),
        ]
        assert data_source.stats_calls == [([POWER.id, SOC.id], "none")]

    async def test_a_failing_function_only_fails_its_items(self):
        data_source = FakeReportDataSource(
            stats=[PointStatValues(point_id=POWER.id, values={"avg": 5.0})],
            function_results={"site-energy-summary": NotFoundError("no active_power point")},
        )
        block = KpiBlock(kind="kpi", id="kpis", items=[
            SiteFunctionKpi(source="site_function", function="site-energy-summary", field="energy_kwh"),
            PointStatKpi(source="point_stat", point_id=POWER.id, stat="avg"),
        ])
        result = await resolve_block(block, block_context(data_source))
        assert isinstance(result, KpiResult)
        assert result.error is None
        assert [(item.value, item.error) for item in result.items] == [(None, "no active_power point"), (5.0, None)]

    async def test_each_function_runs_once_per_block(self):
        data_source = FakeReportDataSource(function_results={"site-poi-power": PoiPower(peak_kw=3.0, series=series(0, "poi", []))})
        block = KpiBlock(kind="kpi", id="kpis", items=[
            SiteFunctionKpi(source="site_function", function="site-poi-power", field="peak_kw"),
            SiteFunctionKpi(source="site_function", function="site-poi-power", field="peak_kw", label="again"),
        ])
        await resolve_block(block, block_context(data_source))
        assert data_source.function_calls == [("site-poi-power", None, None)]


class TestChart:
    async def test_series_in_block_order_with_empty_series_for_missing_points(self):
        data_source = FakeReportDataSource(
            series=[series(POWER.id, "active_power", [1.0, 2.0])],
            function_results={"site-poi-power": PoiPower(peak_kw=3.0, series=series(0, "poi", [3.0]))},
        )
        block = ChartBlock(kind="chart", id="chart", style="step", max_points=300, series=[
            SiteFunctionSeries(source="site_function", function="site-poi-power"), PointSeries(source="point", point_id=SOC.id), PointSeries(source="point", point_id=POWER.id),
        ])
        result = await resolve_block(block, block_context(data_source))
        assert isinstance(result, ChartResult)
        assert result.style == "step"
        assert [(line.name, len(line.timeseries)) for line in result.series] == [("poi", 1), ("soc", 0), ("active_power", 2)]
        assert data_source.function_calls == [("site-poi-power", None, 300)]


class TestPointStatsTable:
    async def test_rows_by_point_then_bucket_with_a_row_for_points_without_readings(self):
        later = WINDOW_START + timedelta(hours=1)
        data_source = FakeReportDataSource(stats=[
            PointStatValues(point_id=POWER.id, bucket_start=later, values={"min": 2.0, "max": 3.0}),
            PointStatValues(point_id=POWER.id, bucket_start=WINDOW_START, values={"min": 0.0, "max": 1.0}),
        ])
        block = PointStatsTableBlock(kind="point_stats_table", id="stats", point_ids=[SOC.id, POWER.id], stats=["max", "count"], bucket="hour")
        result = await resolve_block(block, block_context(data_source))
        assert isinstance(result, PointStatsTableResult)
        assert [(row.point_name, row.device_name, row.bucket_start, row.values) for row in result.rows] == [
            ("soc", "device_1", None, {"max": None, "count": 0.0}),
            ("active_power", "device_1", WINDOW_START, {"max": 1.0, "count": 0.0}),
            ("active_power", "device_1", later, {"max": 3.0, "count": 0.0}),
        ]
        assert result.rows[1].unit == "kW"


class TestAlarmEventsTable:
    async def test_filters_limits_counts_and_measures(self):
        cleared = event(1, 1, WINDOW_START + timedelta(hours=2), WINDOW_START + timedelta(hours=3))
        active = event(2, 1, WINDOW_END - timedelta(minutes=30), None)
        other_device = event(3, 2, WINDOW_START, None)
        data_source = FakeReportDataSource(events=[active, cleared, other_device], alarm_names={5: "bess_trip"})
        block = AlarmEventsTableBlock(kind="alarm_events_table", id="alarms", device_ids=[1], limit=1)
        result = await resolve_block(block, block_context(data_source))
        assert isinstance(result, AlarmEventsTableResult)
        assert result.total_count == 2
        (row,) = result.rows
        assert (row.event_id, row.alarm_name, row.device_name, row.duration_seconds) == (2, "bess_trip", "device_1", 1800.0)

    async def test_severity_filter_and_cleared_duration(self):
        cleared = event(1, None, WINDOW_START, WINDOW_START + timedelta(minutes=5), severity="warning")
        fault = event(2, None, WINDOW_START, None)
        data_source = FakeReportDataSource(events=[fault, cleared])
        result = await resolve_block(AlarmEventsTableBlock(kind="alarm_events_table", id="alarms", severity="warning"), block_context(data_source))
        assert isinstance(result, AlarmEventsTableResult)
        assert [(row.event_id, row.alarm_name, row.device_name, row.duration_seconds) for row in result.rows] == [
            (1, "alarm 5", None, 300.0)
        ]


class TestFailingBlock:
    async def test_is_stored_as_an_error_of_its_kind(self):
        data_source = FakeReportDataSource(function_results={"site-poi-power": NotFoundError("no POI point on this site")})
        block = ChartBlock(kind="chart", id="chart", title="POI", series=[SiteFunctionSeries(source="site_function", function="site-poi-power")])
        result = await resolve_block(block, block_context(data_source))
        assert isinstance(result, ChartResult)
        assert (result.block_id, result.title, result.error, result.series) == ("chart", "POI", "no POI point on this site", [])

    async def test_unexpected_errors_are_not_shown_in_the_report(self):
        data_source = FakeReportDataSource(function_results={"site-poi-power": RuntimeError("connection reset by peer")})
        result = await resolve_block(ChartBlock(kind="chart", id="chart", series=[SiteFunctionSeries(source="site_function", function="site-poi-power")]), block_context(data_source))
        assert result.error == "Could not generate block 'chart'"


class TestTimezone:
    async def test_text_uses_the_site_zone(self):
        result = await resolve_block(TextBlock(kind="text", id="intro", body="{window_start}"), block_context(FakeReportDataSource(), timezone="UTC"))
        assert isinstance(result, TextResult)
        assert result.body == WINDOW_START.astimezone(UTC).strftime("%Y-%m-%d %H:%M")
