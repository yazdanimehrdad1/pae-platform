"""Plot values and gap markers for stored readings, computed in Postgres (see README.md).

The same rule as plot_values.py, so a long window's readings are reduced where they are stored
and only the kept rows reach Python: per point, the window is cut into max_points // 4 slices and
each slice keeps its first, last, lowest and highest reading (an enum or bit point: first, last
and every change of value); both edges of a gap longer than max_gap are kept, and each gap adds
one marker row with a null value at its midpoint. Readings with a null value are left out.

The statement's columns are `point_columns` plus `timestamp` and `derived_value`, newest first
per point, like the raw readings query, so callers build PointReadings from it the same way.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, Select, and_, cast, literal, null, or_, select, union_all
from sqlalchemy import func as sql_func
from sqlalchemy.sql.elements import Label

from helpers.sampling.plot_values import DISCRETE_DATA_TYPES, SAMPLES_PER_SLICE
from schemas.db_models.orm_models import DevicePoint, DevicePointsReading


def plot_values_statement(
    point_columns: Sequence[Label[object] | ColumnElement[object]],
    conditions: Sequence[ColumnElement[bool]],
    start: datetime,
    end: datetime,
    max_points: int,
    max_gap: timedelta,
) -> Select[tuple[object, ...]]:
    """The plot values (and gap markers) of every point matching `conditions` in the window."""
    slices = max(1, max_points // SAMPLES_PER_SLICE)
    slice_seconds = (end - start).total_seconds() / slices
    reading_time = DevicePointsReading.timestamp
    by_point_in_time = {"partition_by": DevicePointsReading.device_point_id, "order_by": reading_time}

    readings = (
        select(
            *point_columns,
            reading_time.label("timestamp"),
            DevicePointsReading.derived_value.label("derived_value"),
            sql_func.floor(
                (sql_func.extract("epoch", reading_time) - literal(start.timestamp())) / literal(slice_seconds)
            ).label("slice"),
            sql_func.lag(reading_time).over(**by_point_in_time).label("previous_time"),
            sql_func.lead(reading_time).over(**by_point_in_time).label("next_time"),
            sql_func.lag(DevicePointsReading.derived_value).over(**by_point_in_time).label("previous_value"),
        )
        .select_from(DevicePointsReading)
        .join(DevicePoint, DevicePointsReading.device_point_id == DevicePoint.id)
        .where(and_(DevicePointsReading.derived_value.is_not(None), *conditions))
    ).subquery("readings")

    in_slice = (readings.c.device_point_id, readings.c.slice)
    ranked = select(
        readings,
        sql_func.row_number().over(partition_by=in_slice, order_by=readings.c.timestamp).label("first_rank"),
        sql_func.row_number().over(partition_by=in_slice, order_by=readings.c.timestamp.desc()).label("last_rank"),
        sql_func.row_number().over(partition_by=in_slice, order_by=readings.c.derived_value).label("low_rank"),
        sql_func.row_number().over(partition_by=in_slice, order_by=readings.c.derived_value.desc()).label("high_rank"),
    ).subquery("ranked")

    max_gap_interval = literal(max_gap)
    gap_before = ranked.c.timestamp - ranked.c.previous_time > max_gap_interval
    gap_after = ranked.c.next_time - ranked.c.timestamp > max_gap_interval
    discrete = ranked.c.data_type.in_(sorted(DISCRETE_DATA_TYPES))
    keep = or_(
        ranked.c.first_rank == 1,
        ranked.c.last_rank == 1,
        and_(~discrete, or_(ranked.c.low_rank == 1, ranked.c.high_rank == 1)),
        and_(discrete, ranked.c.previous_value.is_distinct_from(ranked.c.derived_value), ranked.c.previous_time.is_not(None)),
        gap_before,
        gap_after,
    )
    point_names = [column.key for column in point_columns]
    kept = select(*(ranked.c[name] for name in point_names), ranked.c.timestamp, ranked.c.derived_value).where(keep)
    markers = select(
        *(ranked.c[name] for name in point_names),
        (ranked.c.previous_time + (ranked.c.timestamp - ranked.c.previous_time) / 2).label("timestamp"),
        cast(null(), DevicePointsReading.derived_value.type).label("derived_value"),
    ).where(gap_before)

    both = union_all(kept, markers).subquery("plot_values")
    return select(both).order_by(both.c.device_point_id, both.c.timestamp.desc())
