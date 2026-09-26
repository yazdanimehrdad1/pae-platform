"""Historian reads only Alpha Solar Farm needs."""

from schemas.api_models import PointTimeseries
from schemas.site_profiles import SiteContext, TimeWindow
from site_profiles.common.historian import get_point_series
from utils.exceptions import NotFoundError

POI_ACTIVE_POWER_POINT = "poi_active_power_total"


async def get_poi_active_power(ctx: SiteContext, window: TimeWindow) -> PointTimeseries:
    """
    SAMPLE (site-only query): the point-of-interconnection active power, oldest first.

    At Alpha the POI meter values live on the PV plant controller (device_3), so the
    query looks the point up by name across the site rather than on a fixed device.
    """
    points = ctx.points_named(POI_ACTIVE_POWER_POINT)
    if not points:
        raise NotFoundError(
            f"Site {ctx.site.site_id} has no '{POI_ACTIVE_POWER_POINT}' point on any device"
        )
    poi_point = points[0]
    series_by_point = await get_point_series(ctx, [poi_point], window)
    return series_by_point[poi_point.id]
