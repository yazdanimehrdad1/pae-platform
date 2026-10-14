"""
A generated report (snapshot): every block of its definition resolved to data, stored with the run.

The UI renders a report from this alone, so reopening it never re-reads the readings and shows the
same numbers every time. A block that fails to resolve carries an `error` instead of data; the
rest of the report still renders.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from schemas.api_models.alarms import AlarmSeverity
from schemas.api_models.responses import PointTimeseries
from schemas.reports.definition import PointStat, ReportDefinition

SNAPSHOT_SCHEMA_VERSION = 1


class _BlockResult(BaseModel):
    block_id: str
    title: str | None = None
    error: str | None = Field(None, description="Why the block has no data; null when it resolved")


class TextResult(_BlockResult):
    kind: Literal["text"] = "text"
    body: str = ""


class KpiValue(BaseModel):
    label: str
    value: float | None = Field(None, description="Null when there was nothing to compute it from")
    unit: str | None = None
    error: str | None = Field(None, description="Why this item has no value (e.g. the function failed)")


class KpiResult(_BlockResult):
    kind: Literal["kpi"] = "kpi"
    items: list[KpiValue] = Field(default_factory=list)


class ChartResult(_BlockResult):
    kind: Literal["chart"] = "chart"
    style: Literal["line", "step", "bar"] = "line"
    series: list[PointTimeseries] = Field(
        default_factory=list, description="Oldest sample first; site function series keep the function's own ids"
    )


class PointStatsRow(BaseModel):
    point_id: int
    point_name: str
    device_id: int
    device_name: str
    unit: str | None = None
    bucket_start: datetime | None = Field(None, description="Start of the hour/day (UTC); null for the whole window")
    values: dict[PointStat, float | None] = Field(default_factory=dict)


class PointStatsTableResult(_BlockResult):
    kind: Literal["point_stats_table"] = "point_stats_table"
    stats: list[PointStat] = Field(default_factory=list)
    bucket: Literal["none", "hour", "day"] = "none"
    rows: list[PointStatsRow] = Field(default_factory=list, description="By point (in the block's order), then bucket")


class AlarmEventRow(BaseModel):
    event_id: int
    alarm_name: str
    severity: AlarmSeverity
    device_id: int | None = None
    device_name: str | None = None
    raised_at: datetime
    cleared_at: datetime | None = None
    duration_seconds: float | None = Field(None, description="Raise to clear, or to the window end while active")
    value_at_raise: float | None = None
    message: str


class AlarmEventsTableResult(_BlockResult):
    kind: Literal["alarm_events_table"] = "alarm_events_table"
    rows: list[AlarmEventRow] = Field(default_factory=list)
    total_count: int = Field(0, description="Matching events; more than len(rows) when the block's limit cut them")


BlockResult = Annotated[
    TextResult | KpiResult | ChartResult | PointStatsTableResult | AlarmEventsTableResult,
    Field(discriminator="kind"),
]


class ReportSnapshot(BaseModel):
    """A generated report: the definition it was made from, its window and each block's data."""

    schema_version: Literal[1] = SNAPSHOT_SCHEMA_VERSION
    site_id: int
    site_name: str
    timezone: str = Field(..., description="The site's time zone when it was generated")
    window_start: datetime
    window_end: datetime
    generated_at: datetime
    definition: ReportDefinition
    blocks: list[BlockResult] = Field(default_factory=list, description="One per definition block, same order")
