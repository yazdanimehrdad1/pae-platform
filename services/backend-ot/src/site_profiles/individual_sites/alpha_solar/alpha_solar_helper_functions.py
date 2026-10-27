"""
Alpha Solar Farm's helper functions: calculations and historian reads only this site needs.
The calculations are pure (no DB, no network, no clock); get_poi_active_power reads the
historian through spf_common_get_point_timeseries.
"""

import math
from datetime import datetime

from helpers.sites.site_health import is_alarm_set
from schemas.api_models import DevicePointResponse, PointTimeseries, TimeseriesPoint
from schemas.internal_models import PointReading, TimestampedValue
from schemas.site_profiles import SiteContext, TimeWindow
from site_profiles.common.shared_helper_functions import spf_common_get_point_timeseries
from utils.exceptions import NotFoundError

POI_ACTIVE_POWER_POINT = "poi_active_power_total"
POI_REACTIVE_POWER_POINT = "poi_reactive_power_total"


def count_online_samples(states: list[TimeseriesPoint], online_states: frozenset[int]) -> int:
    """SAMPLE: how many state samples hold a code that counts as available."""
    return sum(1 for s in states if s.value is not None and int(s.value) in online_states)


def set_alarm_points(
    points: list[DevicePointResponse], readings: list[PointReading], oldest: datetime
) -> list[DevicePointResponse]:
    """The points whose latest reading is set (reported and non-zero, like the Sites page health)
    and no older than `oldest`. A stale value doesn't count: losing comms is not a fault. Readings
    are matched to points by id; a point without a reading isn't set."""
    fresh_set_ids = {
        reading.device_point_id
        for reading in readings
        if is_alarm_set(reading) and reading.timestamp is not None and reading.timestamp >= oldest
    }
    return [point for point in points if point.id in fresh_set_ids]


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


def apparent_power_samples(active: PointTimeseries, reactive: PointTimeseries) -> list[TimestampedValue]:
    """SAMPLE: sqrt(P^2 + Q^2) at every poll where both were read. P and Q come from the same
    device, so one poll gives both the same timestamp; a poll missing either gives no value."""
    reactive_by_time = {sample.time: sample.value for sample in reactive.timeseries if sample.value is not None}
    return [
        TimestampedValue(time=sample.time, value=math.hypot(sample.value, reactive_by_time[sample.time]))
        for sample in active.timeseries
        if sample.value is not None and sample.time in reactive_by_time
    ]
