"""An in-memory ReportDataSource for unit tests: canned answers, and a record of what was asked."""

from datetime import datetime

from pydantic import BaseModel

from schemas.api_models import PointTimeseries
from schemas.api_models.alarms import AlarmEventResponse, AlarmSeverity
from schemas.reports.internal import PointStatValues, ReportSiteContext
from utils.exceptions import AppError


class FakeReportDataSource:
    def __init__(
        self,
        site: ReportSiteContext | None = None,
        series: list[PointTimeseries] | None = None,
        stats: list[PointStatValues] | None = None,
        function_results: dict[str, BaseModel | Exception] | None = None,
        events: list[AlarmEventResponse] | None = None,
        alarm_names: dict[int, str] | None = None,
    ) -> None:
        self.site = site
        self.series = series or []
        self.stats = stats or []
        self.function_results = function_results or {}
        self.events = events or []
        self.alarm_names = alarm_names or {}
        self.function_calls: list[tuple[str, int | None, int | None]] = []
        self.stats_calls: list[tuple[list[int], str]] = []

    async def get_site_context(self, site_id: int) -> ReportSiteContext | None:
        return self.site

    async def get_point_series(
        self, site_id: int, point_ids: list[int], start: datetime, end: datetime, max_points: int
    ) -> list[PointTimeseries]:
        return [series for series in self.series if series.id in point_ids]

    async def get_point_stats(
        self, site_id: int, point_ids: list[int], start: datetime, end: datetime, bucket: str, site_timezone: str
    ) -> list[PointStatValues]:
        self.stats_calls.append((point_ids, bucket))
        return [entry for entry in self.stats if entry.point_id in point_ids]

    async def run_site_function(
        self, site_id: int, name: str, start: datetime, end: datetime,
        device_id: int | None = None, max_points: int | None = None,
    ) -> BaseModel:
        self.function_calls.append((name, device_id, max_points))
        result = self.function_results.get(name)
        if result is None:
            raise AppError(f"no canned result for {name}")
        if isinstance(result, Exception):
            raise result
        return result

    async def get_alarm_events(
        self, site_id: int, start: datetime, end: datetime, severity: AlarmSeverity | None = None
    ) -> list[AlarmEventResponse]:
        return [event for event in self.events if severity is None or event.severity == severity]

    async def get_alarm_names(self, site_id: int) -> dict[int, str]:
        return self.alarm_names
