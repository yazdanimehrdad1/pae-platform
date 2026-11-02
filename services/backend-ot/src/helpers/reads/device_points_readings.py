"""Readings of device points, keyed by device_point_id.

NATIVE (and unlinked STANDARDIZED) points are read from device_points_readings. VIRTUAL points are
computed on read from their inputs' stored readings (helpers.virtual_points.resolve); nothing is
stored for them, and any stored rows under a virtual point's id are ignored. The exception is a
VIRTUAL point the site profile owns (profile_point_key): the job profile_point_compute stores its
values (helpers.profile_points), so it is read from device_points_readings too. A linked STANDARDIZED
point (source_point_id, set through PUT .../link) returns its source's stored readings under its
own id and metadata, each value x its scale_factor.

A chart's request (max_points) is sampled by helpers.sampling: every reading of a window up to
3 days, plot values beyond, with gap markers either way (README.md there).
"""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import ColumnElement, and_, select, true
from sqlalchemy import func as sql_func

from db.session import get_session
from helpers.sampling import (
    default_max_gap,
    plot_values_statement,
    sample_readings,
    use_plot_values,
)
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
    linked_points = await get_linked_points_by_ids(point_ids, site_id=site_id, device_id=device_id)
    if linked_points:
        source_latest = await _select_latest(_source_ids(linked_points))
        linked = {reading.device_point_id: reading for reading in _linked_readings(source_latest, linked_points)}
        readings = [linked.get(reading.device_point_id, reading) for reading in readings]
    virtual_points = await get_virtual_points_by_ids(point_ids, site_id=site_id, device_id=device_id)
    if virtual_points:
        computed = await _computed_latest(virtual_points)
        for reading in readings:
            if reading.device_point_id in computed:
                sample = computed[reading.device_point_id]
                reading.timestamp = sample.time if sample else None
                reading.derived_value = sample.value if sample else None
    return readings


async def get_last_successful_poll_times(device_ids: Collection[int]) -> dict[int, datetime]:
    """Per device: when its newest NATIVE reading with a value was stored (its last successful
    poll). A device that has never reported is missing from the result.

    The newest valued reading of each NATIVE point (LATERAL ... LIMIT 1, a backward index step),
    then the newest of those per device, so the cost doesn't grow with the history stored."""
    if not device_ids:
        return {}
    newest_valued = (
        select(DevicePointsReading.timestamp)
        .where(
            DevicePointsReading.device_point_id == DevicePoint.id,
            DevicePointsReading.derived_value.is_not(None),
        )
        .order_by(DevicePointsReading.timestamp.desc())
        .limit(1)
        .lateral("newest_valued")
    )
    statement = (
        select(DevicePoint.device_id, sql_func.max(newest_valued.c.timestamp))
        .select_from(DevicePoint)
        .join(newest_valued, true())
        .where(DevicePoint.device_id.in_(device_ids), DevicePoint.category == "NATIVE")
        .group_by(DevicePoint.device_id)
    )
    async with get_session() as session:
        rows = await session.execute(statement)
        return dict(rows.tuples().all())


async def get_timeseries_by_point_ids(
    point_ids: list[int],
    site_id: int | None = None,
    device_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int | None = 1000,
    max_points: int | None = None,
) -> list[PointReading]:
    """
    Get time-series readings per point, ordered by (device_point_id, timestamp DESC).

    max_points with a start_time and end_time is a chart's request, sampled by helpers.sampling:
    `limit` is ignored, a window up to 3 days returns every reading, a longer one plot values,
    and both get gap markers (readings with derived_value None). Without a window it is ignored.

    Each point yields its most recent `limit` readings, newest-first. This holds whether
    the window comes from `limit` alone or from start_time/end_time — the most recent
    reading is always the first element. `limit=None` returns every reading in the window.
    VIRTUAL points are computed from their inputs' stored readings, in the same shape.

    If point_ids is empty, returns readings for all points belonging to device_id/site_id.
    """
    virtual_points = await get_virtual_points_by_ids(point_ids, site_id=site_id, device_id=device_id)
    linked_points = await get_linked_points_by_ids(point_ids, site_id=site_id, device_id=device_id)
    computed_ids = {point.id for point in virtual_points + linked_points}
    stored_ids = [point_id for point_id in point_ids if point_id not in computed_ids]
    if max_points is not None and start_time is not None and end_time is not None:
        return await _chart_timeseries(
            point_ids, stored_ids, virtual_points, linked_points, site_id, device_id, start_time, end_time, max_points
        )

    readings: list[PointReading] = []
    if stored_ids or not point_ids:
        readings = await _select_timeseries(
            stored_ids, site_id=site_id, device_id=device_id, start_time=start_time,
            end_time=end_time, limit=limit, exclude_point_ids=computed_ids,
        )
    if linked_points:
        source_readings = await _select_timeseries(
            _source_ids(linked_points), start_time=start_time, end_time=end_time, limit=limit
        )
        readings += _linked_readings(source_readings, linked_points)
        readings.sort(key=_by_point_newest_first)
    if virtual_points:
        readings += await _computed_timeseries(virtual_points, start_time, end_time, limit)
        readings.sort(key=_by_point_newest_first)
    return readings


async def _chart_timeseries(
    point_ids: list[int],
    stored_ids: list[int],
    virtual_points: list[DevicePoint],
    linked_points: list[DevicePoint],
    site_id: int | None,
    device_id: int | None,
    start_time: datetime,
    end_time: datetime,
    max_points: int,
) -> list[PointReading]:
    """get_timeseries_by_point_ids for a chart: stored readings (a linked point's are its
    source's) reduced in Postgres when the window takes plot values, virtual points computed in
    full and then sampled."""
    max_gap = default_max_gap()
    computed_ids = {point.id for point in virtual_points + linked_points}
    readings: list[PointReading] = []
    if stored_ids or not point_ids:
        readings = await _chart_stored(stored_ids, site_id, device_id, start_time, end_time, max_points, computed_ids)
    if linked_points:
        source_readings = await _chart_stored(
            _source_ids(linked_points), None, None, start_time, end_time, max_points, ()
        )
        readings += _linked_readings(source_readings, linked_points)
    if virtual_points:
        computed = await _computed_timeseries(virtual_points, start_time, end_time, None)
        readings += sample_readings(computed, start_time, end_time, max_points, max_gap)
    readings.sort(key=_by_point_newest_first)
    return readings


async def get_virtual_points_by_ids(
    point_ids: list[int], site_id: int | None = None, device_id: int | None = None
) -> list[DevicePoint]:
    """The VIRTUAL points computed on read among `point_ids` (all of the device's or site's when
    empty). A profile-owned one has its values stored, so it is read like a NATIVE point."""
    conditions = [DevicePoint.category == "VIRTUAL", DevicePoint.profile_point_key.is_(None)]
    if point_ids:
        conditions.append(DevicePoint.id.in_(point_ids))
    if device_id is not None:
        conditions.append(DevicePoint.device_id == device_id)
    if site_id is not None:
        conditions.append(DevicePoint.site_id == site_id)
    async with get_session() as session:
        result = await session.execute(select(DevicePoint).where(and_(*conditions)))
        return list(result.scalars().all())


async def _chart_stored(
    point_ids: list[int],
    site_id: int | None,
    device_id: int | None,
    start_time: datetime,
    end_time: datetime,
    max_points: int,
    exclude_point_ids: Collection[int],
) -> list[PointReading]:
    """Stored readings for a chart: plot values reduced in Postgres, or every reading sampled."""
    max_gap = default_max_gap()
    if use_plot_values(start_time, end_time, max_points):
        conditions = _reading_conditions(point_ids, site_id, device_id, start_time, end_time, exclude_point_ids)
        statement = plot_values_statement(_POINT_COLUMNS, conditions, start_time, end_time, max_points, max_gap)
        async with get_session() as session:
            result = await session.execute(statement)
            return [PointReading.model_validate(row, from_attributes=True) for row in result.all()]
    stored = await _select_timeseries(
        point_ids, site_id=site_id, device_id=device_id, start_time=start_time,
        end_time=end_time, limit=None, exclude_point_ids=exclude_point_ids,
    )
    return sample_readings(stored, start_time, end_time, max_points, max_gap)


async def get_linked_points_by_ids(
    point_ids: list[int], site_id: int | None = None, device_id: int | None = None
) -> list[DevicePoint]:
    """The linked STANDARDIZED points among `point_ids` (all of the device's or site's when empty)."""
    conditions = [DevicePoint.category == "STANDARDIZED", DevicePoint.source_point_id.is_not(None)]
    if point_ids:
        conditions.append(DevicePoint.id.in_(point_ids))
    if device_id is not None:
        conditions.append(DevicePoint.device_id == device_id)
    if site_id is not None:
        conditions.append(DevicePoint.site_id == site_id)
    async with get_session() as session:
        result = await session.execute(select(DevicePoint).where(and_(*conditions)))
        return list(result.scalars().all())


def _source_ids(linked_points: list[DevicePoint]) -> list[int]:
    return sorted({point.source_point_id for point in linked_points if point.source_point_id is not None})


def _linked_readings(source_readings: list[PointReading], linked_points: list[DevicePoint]) -> list[PointReading]:
    """Each source reading as a reading of every point linked to it: the linked point's id and
    metadata, the value x its scale_factor. A gap marker (value None) stays a gap marker."""
    by_source: dict[int, list[DevicePoint]] = {}
    for point in linked_points:
        if point.source_point_id is not None:
            by_source.setdefault(point.source_point_id, []).append(point)
    readings: list[PointReading] = []
    for reading in source_readings:
        for point in by_source.get(reading.device_point_id, []):
            scale = point.scale_factor if point.scale_factor is not None else 1.0
            readings.append(PointReading(
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
                timestamp=reading.timestamp,
                derived_value=reading.derived_value * scale if reading.derived_value is not None else None,
            ))
    return readings


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
    """The newest stored reading per point (LEFT JOIN: a point without readings gets None).

    One backward index step per point (LATERAL ... LIMIT 1 on (device_point_id, timestamp)), so
    the cost doesn't grow with the history stored. Joining every reading and keeping the first
    (DISTINCT ON) scanned the whole table, and the alarm job runs this every poll interval.
    """
    point_conditions = []
    if point_ids:
        point_conditions.append(DevicePoint.id.in_(point_ids))
    if device_id is not None:
        point_conditions.append(DevicePoint.device_id == device_id)
    if site_id is not None:
        point_conditions.append(DevicePoint.site_id == site_id)

    newest_reading = (
        select(DevicePointsReading.timestamp, DevicePointsReading.derived_value)
        .where(DevicePointsReading.device_point_id == DevicePoint.id)
        .order_by(DevicePointsReading.timestamp.desc())
        .limit(1)
        .lateral("newest_reading")
    )
    statement = (
        select(*_POINT_COLUMNS, newest_reading.c.timestamp, newest_reading.c.derived_value)
        .select_from(DevicePoint)
        .outerjoin(newest_reading, true())
        .where(and_(*point_conditions) if point_conditions else true())
        .order_by(DevicePoint.id)
    )
    async with get_session() as session:
        result = await session.execute(statement)
        return [PointReading.model_validate(row, from_attributes=True) for row in result.all()]


def _reading_conditions(
    point_ids: list[int],
    site_id: int | None,
    device_id: int | None,
    start_time: datetime | None,
    end_time: datetime | None,
    exclude_point_ids: Collection[int],
) -> list[ColumnElement[bool]]:
    """Which stored readings a timeseries query covers (shared by the raw and plot-value reads)."""
    conditions: list[ColumnElement[bool]] = []
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
    return conditions


async def _select_timeseries(
    point_ids: list[int],
    site_id: int | None = None,
    device_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int | None = 1000,
    exclude_point_ids: Collection[int] = (),
) -> list[PointReading]:
    """Stored readings per point, newest-first, the newest `limit` per point.

    Per point, one backward index range scan (LATERAL on (device_point_id, timestamp)) that stops
    after `limit` rows, so a limit without a window costs `limit` rows, not the point's history.
    """
    point_conditions: list[ColumnElement[bool]] = []
    if point_ids:
        point_conditions.append(DevicePoint.id.in_(point_ids))
    if exclude_point_ids:
        point_conditions.append(DevicePoint.id.not_in(exclude_point_ids))
    if device_id is not None:
        point_conditions.append(DevicePoint.device_id == device_id)
    if site_id is not None:
        point_conditions.append(DevicePoint.site_id == site_id)
    window_conditions: list[ColumnElement[bool]] = [DevicePointsReading.device_point_id == DevicePoint.id]
    if start_time is not None:
        window_conditions.append(DevicePointsReading.timestamp >= start_time)
    if end_time is not None:
        window_conditions.append(DevicePointsReading.timestamp <= end_time)

    point_readings = (
        select(DevicePointsReading.timestamp, DevicePointsReading.derived_value)
        .where(*window_conditions)
        .order_by(DevicePointsReading.timestamp.desc())
    )
    if limit is not None:
        point_readings = point_readings.limit(limit)
    newest = point_readings.lateral("point_readings")

    statement = (
        select(*_POINT_COLUMNS, newest.c.timestamp, newest.c.derived_value)
        .select_from(DevicePoint)
        .join(newest, true())
        .where(and_(*point_conditions) if point_conditions else true())
        .order_by(DevicePoint.id, newest.c.timestamp.desc())
    )
    async with get_session() as session:
        result = await session.execute(statement)
        return [PointReading.model_validate(row, from_attributes=True) for row in result.all()]
