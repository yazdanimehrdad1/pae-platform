"""
Historian reads any site can reuse. Wraps the existing readings queries
(helpers/reads/device_points_readings.py) and returns typed series for calculations.
"""

from helpers.reads.device_points_readings import get_timeseries_by_point_ids
from schemas.api_models import DevicePointResponse, PointTimeseries, TimeseriesPoint
from schemas.site_profiles import SiteContext, TimeWindow


async def get_point_series(
    ctx: SiteContext, points: list[DevicePointResponse], window: TimeWindow
) -> dict[int, PointTimeseries]:
    """
    Every reading of `points` inside `window`, keyed by point id, OLDEST FIRST, with
    timestamps rendered in the window's display zone. A point with no readings in the
    window is still present, with an empty series.
    """
    series_by_point = {
        point.id: PointTimeseries(
            id=point.id,
            name=point.name,
            data_type=point.data_type,
            unit=point.unit,
            point_class=point.point_class,
            severity=point.severity,
        )
        for point in points
    }
    if not points:
        return series_by_point

    rows = await get_timeseries_by_point_ids(
        list(series_by_point),
        site_id=ctx.site.site_id,
        start_time=window.start_time,
        end_time=window.end_time,
        limit=None,
    )
    for row in reversed(rows):  # rows come newest-first per point
        series = series_by_point[row["device_point_id"]]
        series.timeseries.append(
            TimeseriesPoint(time=window.display(row["timestamp"]), value=row["derived_value"])
        )
        series.count += 1
    return series_by_point
