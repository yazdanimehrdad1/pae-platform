"""Readings of device points, keyed by device_point_id.

NATIVE (and STANDARDIZED) points are read from device_points_readings. VIRTUAL points are computed
on read from their inputs' stored readings (helpers.virtual_points.resolve); nothing is stored
for them, and any stored rows under a virtual point's id are ignored.
"""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy import func as sql_func

from db.session import get_session
from helpers.virtual_points.definition import referenced_point_ids
from helpers.virtual_points.resolve import evaluate_latest, evaluate_series, input_max_gap
from schemas.api_models.virtual_points import VirtualDefinition
from schemas.db_models.orm_models import DevicePoint, DevicePointsReading
from schemas.internal_models import PointReading, TimestampedValue

# The point columns every reading carries, labelled as PointReading's fields.
_POINT_COLUMNS = (
    DevicePoint.id.label("device_point_id"),
    DevicePoint.address.label("register_address"),
    DevicePoint.name,
    DevicePoint.data_type,
    DevicePoint.size,
    DevicePoint.unit,
    DevicePoint.scale_factor,
    DevicePoint.bitfield_detail,
    DevicePoint.enum_detail,
    DevicePoint.point_class,
    DevicePoint.severity,
)


async def get_latest_readings_by_point_ids(
    point_ids: list[int],
    site_id: int | None = None,
    device_id: int | None = None,
) -> list[PointReading]:
    """
    Get the single latest reading per point: stored for NATIVE/STANDARDIZED points, computed from
    the inputs' latest stored readings for VIRTUAL points.

    Always returns ALL device points for the device (LEFT JOIN), so points that have never been
    polled (or a virtual point whose inputs are missing or stale) appear with timestamp=None and
    derived_value=None. If point_ids is provided, only those points are returned.
    """
    readings = await _select_latest(point_ids, site_id=site_id, device_id=device_id)
    virtual_points = await get_virtual_points_by_ids(point_ids, site_id=site_id, device_id=device_id)
    if virtual_points:
        computed = await _computed_latest(virtual_points)
        for reading in readings:
            if reading.device_point_id in computed:
                sample = computed[reading.device_point_id]
                reading.timestamp = sample.time if sample else None
                reading.derived_value = sample.value if sample else None
    return readings


async def get_timeseries_by_point_ids(
    point_ids: list[int],
    site_id: int | None = None,
    device_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int | None = 1000,
) -> list[PointReading]:
    """
    Get time-series readings per point, ordered by (device_point_id, timestamp DESC).

    Each point yields its most recent `limit` readings, newest-first. This holds whether
    the window comes from `limit` alone or from start_time/end_time — the most recent
    reading is always the first element. `limit=None` returns every reading in the window.
    VIRTUAL points are computed from their inputs' stored readings, in the same shape.

    If point_ids is empty, returns readings for all points belonging to device_id/site_id.
    """
    virtual_points = await get_virtual_points_by_ids(point_ids, site_id=site_id, device_id=device_id)
    virtual_ids = {point.id for point in virtual_points}
    stored_ids = [point_id for point_id in point_ids if point_id not in virtual_ids]

    readings: list[PointReading] = []
    if stored_ids or not point_ids:
        readings = await _select_timeseries(
            stored_ids, site_id=site_id, device_id=device_id, start_time=start_time,
            end_time=end_time, limit=limit, exclude_point_ids=virtual_ids,
        )
    if virtual_points:
        readings += await _computed_timeseries(virtual_points, start_time, end_time, limit)
        readings.sort(key=_by_point_newest_first)
    return readings


async def get_virtual_points_by_ids(
    point_ids: list[int], site_id: int | None = None, device_id: int | None = None
) -> list[DevicePoint]:
    """The VIRTUAL points among `point_ids` (all of the device's or site's when empty)."""
    conditions = [DevicePoint.category == "VIRTUAL"]
    if point_ids:
        conditions.append(DevicePoint.id.in_(point_ids))
    if device_id is not None:
        conditions.append(DevicePoint.device_id == device_id)
    if site_id is not None:
        conditions.append(DevicePoint.site_id == site_id)
    async with get_session() as session:
        result = await session.execute(select(DevicePoint).where(and_(*conditions)))
        return list(result.scalars().all())


def _by_point_newest_first(reading: PointReading) -> tuple[int, float]:
    return reading.device_point_id, -(reading.timestamp.timestamp() if reading.timestamp else 0.0)


def _definitions(virtual_points: list[DevicePoint]) -> dict[int, VirtualDefinition]:
    """Definitions by point id. The column loads as the parsed model; a point without one (or
    with a stored one that no longer parses, loaded as None) computes nothing."""
    return {point.id: point.virtual_definition for point in virtual_points if point.virtual_definition is not None}


def _input_ids(definitions: dict[int, VirtualDefinition]) -> list[int]:
    return sorted({point_id for definition in definitions.values() for point_id in referenced_point_ids(definition)})


def _as_timestamped_value(reading: PointReading) -> TimestampedValue | None:
    if reading.timestamp is None or reading.derived_value is None:
        return None
    return TimestampedValue(time=reading.timestamp, value=reading.derived_value)


async def _computed_latest(virtual_points: list[DevicePoint]) -> dict[int, TimestampedValue | None]:
    definitions = _definitions(virtual_points)
    input_ids = _input_ids(definitions)
    latest_inputs = {reading.device_point_id: _as_timestamped_value(reading) for reading in await _select_latest(input_ids)} if input_ids else {}
    max_gap = input_max_gap()
    return {
        point.id: evaluate_latest(definitions[point.id], latest_inputs, max_gap) if point.id in definitions else None
        for point in virtual_points
    }


async def _computed_timeseries(
    virtual_points: list[DevicePoint],
    start_time: datetime | None,
    end_time: datetime | None,
    limit: int | None,
) -> list[PointReading]:
    definitions = _definitions(virtual_points)
    input_ids = _input_ids(definitions)
    if not input_ids:
        return []
    max_gap = input_max_gap()
    # Read from max_gap before the window so the first output can carry an earlier value. With a
    # limit, each input's newest limit+1 rows cover the newest `limit` outputs plus that carry.
    input_readings = await _select_timeseries(
        input_ids,
        start_time=start_time - max_gap if start_time is not None else None,
        end_time=end_time,
        limit=limit + 1 if limit is not None else None,
    )
    inputs: dict[int, list[TimestampedValue]] = {}
    for reading in input_readings:
        sample = _as_timestamped_value(reading)
        if sample is not None:
            inputs.setdefault(reading.device_point_id, []).append(sample)

    readings: list[PointReading] = []
    for point in virtual_points:
        if point.id not in definitions:
            continue
        in_window = [
            sample for sample in evaluate_series(definitions[point.id], inputs, max_gap)
            if (start_time is None or sample.time >= start_time) and (end_time is None or sample.time <= end_time)
        ]
        newest_first = in_window[::-1]
        readings += [_virtual_reading(point, sample) for sample in (newest_first[:limit] if limit is not None else newest_first)]
    return readings


def _virtual_reading(point: DevicePoint, sample: TimestampedValue) -> PointReading:
    return PointReading(
        device_point_id=point.id,
        register_address=point.address,
        name=point.name,
        data_type=point.data_type,
        size=point.size,
        unit=point.unit,
        scale_factor=point.scale_factor,
        bitfield_detail=point.bitfield_detail,
        enum_detail=point.enum_detail,
        point_class=point.point_class,
        severity=point.severity,
        timestamp=sample.time,
        derived_value=sample.value,
    )


async def _select_latest(
    point_ids: list[int],
    site_id: int | None = None,
    device_id: int | None = None,
) -> list[PointReading]:
    """The newest stored reading per point (LEFT JOIN: a point without readings gets None)."""
    point_conditions = []
    if point_ids:
        point_conditions.append(DevicePoint.id.in_(point_ids))
    if device_id is not None:
        point_conditions.append(DevicePoint.device_id == device_id)
    if site_id is not None:
        point_conditions.append(DevicePoint.site_id == site_id)

    statement = (
        select(*_POINT_COLUMNS, DevicePointsReading.timestamp, DevicePointsReading.derived_value)
        .outerjoin(DevicePointsReading, DevicePoint.id == DevicePointsReading.device_point_id)
        .where(and_(*point_conditions) if point_conditions else True)
        .distinct(DevicePoint.id)
        .order_by(DevicePoint.id, DevicePointsReading.timestamp.desc())
    )
    async with get_session() as session:
        result = await session.execute(statement)
        return [PointReading.model_validate(row, from_attributes=True) for row in result.all()]


async def _select_timeseries(
    point_ids: list[int],
    site_id: int | None = None,
    device_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int | None = 1000,
    exclude_point_ids: Collection[int] = (),
) -> list[PointReading]:
    """Stored readings per point, newest-first, the newest `limit` per point."""
    conditions = []
    if point_ids:
        conditions.append(DevicePointsReading.device_point_id.in_(point_ids))
    if exclude_point_ids:
        conditions.append(DevicePointsReading.device_point_id.not_in(exclude_point_ids))
    if device_id is not None:
        conditions.append(DevicePointsReading.device_id == device_id)
    if site_id is not None:
        conditions.append(DevicePointsReading.site_id == site_id)
    if start_time is not None:
        conditions.append(DevicePointsReading.timestamp >= start_time)
    if end_time is not None:
        conditions.append(DevicePointsReading.timestamp <= end_time)

    rank_subq = (
        select(
            *_POINT_COLUMNS,
            DevicePointsReading.timestamp,
            DevicePointsReading.derived_value,
            sql_func.row_number().over(
                partition_by=DevicePointsReading.device_point_id,
                order_by=DevicePointsReading.timestamp.desc(),
            ).label("rn"),
        )
        .select_from(DevicePointsReading)
        .join(DevicePoint, DevicePointsReading.device_point_id == DevicePoint.id)
        .where(and_(*conditions) if conditions else True)
    ).subquery()

    statement = select(rank_subq).order_by(rank_subq.c.device_point_id, rank_subq.c.timestamp.desc())
    if limit is not None:
        statement = statement.where(rank_subq.c.rn <= limit)
    async with get_session() as session:
        result = await session.execute(statement)
        return [PointReading.model_validate(row, from_attributes=True) for row in result.all()]
