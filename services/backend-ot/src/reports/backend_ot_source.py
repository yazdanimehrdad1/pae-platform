"""
The reports module's data source inside backend-ot: reads through backend-ot's own helpers.

The only module in src/reports/ that reads backend-ot's data (sites, devices, readings, alarms,
site profiles). Everything else in src/reports/ goes through ReportDataSource.
"""

import types
import typing
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy import func as sql_func
from sqlalchemy.dialects.postgresql import aggregate_order_by, array_agg

import db.devices as devices_db
import db.sites as sites_db
from api.controllers.site_functions import run_site_endpoint
from db.session import get_session
from helpers.alarms.definitions import list_alarm_definitions
from helpers.alarms.events import query_alarm_events
from helpers.common.date_time import resolve_timezone
from helpers.reads.device_points_readings import (
    get_timeseries_by_point_ids,
    get_virtual_points_by_ids,
)
from reports.data_source import StatsBucket
from reports.stats import compute_point_stats
from schemas.api_models import PointTimeseries, TimeseriesPoint
from schemas.api_models.alarms import AlarmEventResponse, AlarmSeverity
from schemas.db_models.orm_models import DevicePointsReading
from schemas.reports.api import ReportSiteFunction
from schemas.reports.definition import PointStat
from schemas.reports.internal import PointStatValues, ReportSiteContext
from schemas.site_profiles import TimeWindowParams
from site_profiles.profile_registry import get_site_profile

_NUMERIC_TYPES = {int, float}


def numeric_fields(model: type[BaseModel]) -> list[str]:
    """Top-level int/float fields of a result model (optional ones too), ids left out: what a KPI
    can show from a site function."""
    names: list[str] = []
    for name, field in model.model_fields.items():
        if name == "id" or name.endswith("_id"):
            continue
        annotation = field.annotation
        is_union = typing.get_origin(annotation) in (typing.Union, types.UnionType)
        members = set(typing.get_args(annotation)) if is_union else {annotation}
        members.discard(type(None))
        if members and members <= _NUMERIC_TYPES:
            names.append(name)
    return names


class BackendOtReportSource:
    """ReportDataSource over backend-ot's database and site profiles, in process."""

    async def get_site_context(self, site_id: int) -> ReportSiteContext | None:
        site = await sites_db.get_site_by_id(site_id)
        if site is None:
            return None
        functions: list[ReportSiteFunction] = []
        if site.profile is not None:
            functions = [
                ReportSiteFunction(
                    name=endpoint.name,
                    kind=endpoint.kind,
                    output=endpoint.output,
                    summary=endpoint.summary,
                    device_types=list(endpoint.device_types),
                    numeric_fields=numeric_fields(endpoint.response_model),
                )
                for endpoint in get_site_profile(site.profile).endpoints
            ]
        devices = await devices_db.get_all_devices(site_id)
        return ReportSiteContext(site=site, devices=devices, functions=functions)

    async def get_point_series(
        self, site_id: int, point_ids: list[int], start: datetime, end: datetime, max_points: int
    ) -> list[PointTimeseries]:
        if not point_ids:
            return []
        readings = await get_timeseries_by_point_ids(
            point_ids, site_id=site_id, start_time=start, end_time=end, max_points=max_points
        )
        series_by_point: dict[int, PointTimeseries] = {}
        for reading in reversed(readings):  # newest first per point; the series keep oldest first
            if reading.timestamp is None:
                continue
            series = series_by_point.get(reading.device_point_id)
            if series is None:
                series = PointTimeseries.model_validate(reading.model_dump())
                series_by_point[reading.device_point_id] = series
            series.timeseries.append(TimeseriesPoint(time=reading.timestamp, value=reading.derived_value))
            series.count += 1
        return [series_by_point[point_id] for point_id in point_ids if point_id in series_by_point]

    async def get_point_stats(
        self, site_id: int, point_ids: list[int], start: datetime, end: datetime,
        bucket: StatsBucket, site_timezone: str,
    ) -> list[PointStatValues]:
        if not point_ids:
            return []
        virtual_ids = {point.id for point in await get_virtual_points_by_ids(point_ids, site_id=site_id)}
        stored_ids = [point_id for point_id in point_ids if point_id not in virtual_ids]
        stats = await _stored_point_stats(site_id, stored_ids, start, end, bucket, site_timezone)
        if virtual_ids:
            stats += await _virtual_point_stats(site_id, sorted(virtual_ids), start, end, bucket, site_timezone)
        return stats

    async def run_site_function(
        self, site_id: int, name: str, start: datetime, end: datetime,
        device_id: int | None = None, max_points: int | None = None,
    ) -> BaseModel:
        params = TimeWindowParams(start_time=start, end_time=end)
        return await run_site_endpoint(site_id, name, params, device_id=device_id, max_points=max_points)

    async def get_alarm_events(
        self, site_id: int, start: datetime, end: datetime, severity: AlarmSeverity | None = None
    ) -> list[AlarmEventResponse]:
        return await query_alarm_events(site_id, start, end, severity=severity)

    async def get_alarm_names(self, site_id: int) -> dict[int, str]:
        return {alarm.id: alarm.name for alarm in await list_alarm_definitions(site_id, include_deleted=True)}


async def _stored_point_stats(
    site_id: int, point_ids: list[int], start: datetime, end: datetime, bucket: StatsBucket, site_timezone: str
) -> list[PointStatValues]:
    """Statistics computed in Postgres from device_points_readings, bucketed by local hour/day."""
    if not point_ids:
        return []
    value = DevicePointsReading.derived_value
    timestamp = DevicePointsReading.timestamp
    bucket_column = (
        sql_func.date_trunc(bucket, timestamp, site_timezone).label("bucket_start")
        if bucket != "none"
        else None
    )
    columns = [
        DevicePointsReading.device_point_id.label("point_id"),
        sql_func.min(value).label("min"),
        sql_func.max(value).label("max"),
        sql_func.avg(value).label("avg"),
        sql_func.count(value).label("count"),
        array_agg(aggregate_order_by(value, timestamp.asc()))[1].label("first"),
        array_agg(aggregate_order_by(value, timestamp.desc()))[1].label("last"),
    ]
    group_by = [DevicePointsReading.device_point_id]
    if bucket_column is not None:
        columns.append(bucket_column)
        group_by.append(bucket_column)
    statement = (
        select(*columns)
        .where(and_(
            DevicePointsReading.site_id == site_id,
            DevicePointsReading.device_point_id.in_(point_ids),
            timestamp >= start,
            timestamp < end,
            value.is_not(None),
        ))
        .group_by(*group_by)
        .order_by(*group_by)
    )
    stat_names: tuple[PointStat, ...] = ("min", "max", "avg", "first", "last", "count")
    async with get_session() as session:
        rows = (await session.execute(statement)).mappings().all()
    return [
        PointStatValues(
            point_id=row["point_id"],
            bucket_start=row["bucket_start"] if bucket_column is not None else None,
            values={name: float(row[name]) if row[name] is not None else None for name in stat_names},
        )
        for row in rows
    ]


async def _virtual_point_stats(
    site_id: int, point_ids: list[int], start: datetime, end: datetime, bucket: StatsBucket, site_timezone: str
) -> list[PointStatValues]:
    """Virtual points have no stored readings: compute them over the window, then the statistics."""
    readings = await get_timeseries_by_point_ids(point_ids, site_id=site_id, start_time=start, end_time=end, limit=None)
    samples: dict[int, list[tuple[datetime, float]]] = {point_id: [] for point_id in point_ids}
    for reading in readings:
        if reading.timestamp is not None and reading.derived_value is not None and reading.timestamp < end:
            samples[reading.device_point_id].append((reading.timestamp, reading.derived_value))
    zone = resolve_timezone(site_timezone)
    return [
        stats
        for point_id in point_ids
        for stats in compute_point_stats(point_id, samples[point_id], bucket, zone)
    ]
