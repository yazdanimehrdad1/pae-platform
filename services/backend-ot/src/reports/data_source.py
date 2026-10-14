"""
The one door between the reports module and the data it reports on.

Everything a report reads (the site and its points, readings, statistics, site functions, alarm
events) goes through a ReportDataSource. backend_ot_source.py is the in-process implementation, the only
file in src/reports/ that reads backend-ot's data. The rest uses only the module's own tables and
shared plumbing (the DB session, errors, logging). To run reports as a separate service, implement
this protocol over backend-ot's HTTP API and give the module its own database connection.
"""

from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from schemas.api_models import PointTimeseries
from schemas.api_models.alarms import AlarmEventResponse, AlarmSeverity
from schemas.reports.internal import PointStatValues, ReportSiteContext

StatsBucket = Literal["none", "hour", "day"]


@runtime_checkable
class ReportDataSource(Protocol):
    async def get_site_context(self, site_id: int) -> ReportSiteContext | None:
        """The site, its active devices and points, and its profile's functions; None if no such
        active site."""
        ...

    async def get_point_series(
        self, site_id: int, point_ids: list[int], start: datetime, end: datetime, max_points: int
    ) -> list[PointTimeseries]:
        """Each point's readings in [start, end], oldest first, sampled to about max_points (gap
        markers have a null value). Points without readings are left out."""
        ...

    async def get_point_stats(
        self, site_id: int, point_ids: list[int], start: datetime, end: datetime,
        bucket: StatsBucket, site_timezone: str,
    ) -> list[PointStatValues]:
        """Statistics of each point's non-null readings in [start, end): one entry per point (bucket
        none), or per point and local hour/day that has readings."""
        ...

    async def run_site_function(
        self, site_id: int, name: str, start: datetime, end: datetime,
        device_id: int | None = None, max_points: int | None = None,
    ) -> BaseModel:
        """The site function's result over [start, end] (series sampled to max_points when given)."""
        ...

    async def get_alarm_events(
        self, site_id: int, start: datetime, end: datetime, severity: AlarmSeverity | None = None
    ) -> list[AlarmEventResponse]:
        """Alarm events that overlap [start, end], newest raise first."""
        ...

    async def get_alarm_names(self, site_id: int) -> dict[int, str]:
        """Alarm name by definition id, retired profile alarms included."""
        ...
