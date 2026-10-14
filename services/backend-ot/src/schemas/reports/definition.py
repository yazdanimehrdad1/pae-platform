"""
What a report contains: its time window and its blocks (a report definition).

A template stores one definition; a run copies the definition it was made from, so a stored
report keeps showing what it was generated with even after its template changes. Blocks are a
discriminated union on `kind`; each kind has one resolver in src/reports/blocks/ that turns it
into a block result (schemas.reports.snapshot).
"""

import re
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from helpers.common.date_time import TimeRange
from schemas.api_models.alarms import AlarmSeverity

DEFINITION_SCHEMA_VERSION = 1

MAX_BLOCKS = 30
MAX_CHART_SERIES = 8
MAX_KPI_ITEMS = 12
MAX_TABLE_POINTS = 20
MIN_CHART_POINTS = 100  # helpers.sampling.policy.MIN_PLOT_POINTS (not imported: it would import the ORM)
MAX_CHART_POINTS = 2000
DEFAULT_CHART_POINTS = 500
MAX_ALARM_ROWS = 1000

BLOCK_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

PointStat = Literal["min", "max", "avg", "first", "last", "count"]
"""Statistics of a point's non-null readings in the window: avg is the plain mean of the samples
(not time-weighted), first/last are the oldest/newest values, count the number of samples."""

DEFAULT_TABLE_STATS: list[PointStat] = ["min", "max", "avg", "last"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Window ------------------------------------------------------------------------------


class RollingWindow(_Strict):
    """The `duration` ending when the report runs (e.g. the last 1D)."""

    kind: Literal["rolling"]
    duration: TimeRange = Field(..., description="1H, 6H, 12H, 1D, 2D, 3D, 1W, 1M (30 days) or 3M (90 days)")


class CalendarWindow(_Strict):
    """A whole day, week (Monday to Monday) or month in the site's time zone. offset -1 is the
    previous one (yesterday, last week, last month); 0 is the current one, up to now."""

    kind: Literal["calendar"]
    period: Literal["day", "week", "month"]
    offset: int = Field(-1, ge=-36, le=0, description="0: the current period so far; -1: the previous one; -2: the one before")


class FixedWindow(_Strict):
    """Explicit bounds, with a UTC offset."""

    kind: Literal["fixed"]
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time need a UTC offset")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


ReportWindow = Annotated[RollingWindow | CalendarWindow | FixedWindow, Field(discriminator="kind")]


# --- Blocks ------------------------------------------------------------------------------


class _Block(_Strict):
    id: str = Field(..., description="Identifier within the report: lower-case letters, digits, underscore")
    title: str | None = Field(None, max_length=200)

    @field_validator("id")
    @classmethod
    def _check_id(cls, block_id: str) -> str:
        if not BLOCK_ID_PATTERN.match(block_id):
            raise ValueError("id must start with a letter and use only a-z, 0-9 and _ (at most 40 characters)")
        return block_id


class TextBlock(_Block):
    """A paragraph with variables filled in: the site's ({site_name}, {window_start}, ...), and any
    device's or point's on the site ({device:12.name}, {point:34.max}). See reports/text_variables.py."""

    kind: Literal["text"]
    body: str = Field(..., min_length=1, max_length=5000)


class PointStatKpi(_Strict):
    """One statistic of one point over the window."""

    source: Literal["point_stat"]
    label: str | None = Field(None, max_length=100, description="Defaults to '<point> <stat>'")
    point_id: int
    stat: PointStat


class SiteFunctionKpi(_Strict):
    """One numeric field of a site function's result over the window (e.g. energy_kwh of
    site-energy-summary). The report catalog lists each function's numeric fields."""

    source: Literal["site_function"]
    label: str | None = Field(None, max_length=100, description="Defaults to the field name")
    function: str = Field(..., min_length=1, max_length=100)
    device_id: int | None = Field(None, description="Required for a device function, not allowed otherwise")
    field: str = Field(..., min_length=1, max_length=100)


KpiItem = Annotated[PointStatKpi | SiteFunctionKpi, Field(discriminator="source")]


class KpiBlock(_Block):
    """A row of headline numbers."""

    kind: Literal["kpi"]
    items: list[KpiItem] = Field(..., min_length=1, max_length=MAX_KPI_ITEMS)


class PointSeries(_Strict):
    source: Literal["point"]
    point_id: int


class SiteFunctionSeries(_Strict):
    """Every series a series site function returns (e.g. site-poi-power)."""

    source: Literal["site_function"]
    function: str = Field(..., min_length=1, max_length=100)
    device_id: int | None = Field(None, description="Required for a device function, not allowed otherwise")


ChartSeriesSource = Annotated[PointSeries | SiteFunctionSeries, Field(discriminator="source")]


class ChartBlock(_Block):
    """A time chart of points and series site functions over the window."""

    kind: Literal["chart"]
    series: list[ChartSeriesSource] = Field(..., min_length=1, max_length=MAX_CHART_SERIES)
    style: Literal["line", "step", "bar"] = "line"
    max_points: int = Field(
        DEFAULT_CHART_POINTS, ge=MIN_CHART_POINTS, le=MAX_CHART_POINTS,
        description="Points per series kept in the stored report (sampled like the historian's charts)",
    )


class PointStatsTableBlock(_Block):
    """A table of statistics per point, for the whole window or per hour/day (site time)."""

    kind: Literal["point_stats_table"]
    point_ids: list[int] = Field(..., min_length=1, max_length=MAX_TABLE_POINTS)
    stats: list[PointStat] = Field(default_factory=lambda: list(DEFAULT_TABLE_STATS), min_length=1)
    bucket: Literal["none", "hour", "day"] = "none"

    @field_validator("stats")
    @classmethod
    def _unique_stats(cls, stats: list[PointStat]) -> list[PointStat]:
        if len(set(stats)) != len(stats):
            raise ValueError("stats must not repeat")
        return stats


class AlarmEventsTableBlock(_Block):
    """The alarm events that overlap the window, newest raise first."""

    kind: Literal["alarm_events_table"]
    severity: AlarmSeverity | None = Field(None, description="Only this severity; null for both")
    device_ids: list[int] = Field(default_factory=list, max_length=50, description="Only these devices; empty for all")
    limit: int = Field(200, ge=1, le=MAX_ALARM_ROWS)


ReportBlock = Annotated[
    TextBlock | KpiBlock | ChartBlock | PointStatsTableBlock | AlarmEventsTableBlock,
    Field(discriminator="kind"),
]

BlockKind = Literal["text", "kpi", "chart", "point_stats_table", "alarm_events_table"]


class ReportDefinition(_Strict):
    """A report: the window it covers and its blocks, in order."""

    schema_version: Literal[1] = DEFINITION_SCHEMA_VERSION
    window: ReportWindow
    blocks: list[ReportBlock] = Field(..., min_length=1, max_length=MAX_BLOCKS)

    @model_validator(mode="after")
    def _unique_block_ids(self) -> Self:
        block_ids = [block.id for block in self.blocks]
        duplicates = sorted({block_id for block_id in block_ids if block_ids.count(block_id) > 1})
        if duplicates:
            raise ValueError(f"block ids must be unique: {', '.join(duplicates)}")
        return self
