"""
Alpha Solar Farm's helper functions: calculations and historian reads only this site needs.
The calculations are pure (no DB, no network, no clock); get_poi_active_power reads the
historian through spf_common_get_point_timeseries.
"""

from schemas.api_models import PointTimeseries, TimeseriesPoint
from schemas.site_profiles import SiteContext, TimeWindow
from site_profiles.common.shared_helper_functions import spf_common_get_point_timeseries
from utils.exceptions import NotFoundError

POI_ACTIVE_POWER_POINT = "poi_active_power_total"


def count_online_samples(states: list[TimeseriesPoint], online_states: frozenset[int]) -> int:
    """SAMPLE: how many state samples hold a code that counts as available."""
    return sum(1 for s in states if s.value is not None and int(s.value) in online_states)


def availability_pct(online_samples: int, total_samples: int) -> float | None:
    """Share of samples that were online, in percent; None when there are no samples."""
    return online_samples / total_samples * 100 if total_samples else None


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
    series_by_point = await spf_common_get_point_timeseries(ctx, [poi_point], window)
    return series_by_point[poi_point.id]
