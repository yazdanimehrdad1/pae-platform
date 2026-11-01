"""
Calculations on SPF points (site_profiles/declarations/spf_point.py), shared by every site.

spf_common_sum_points is the whole calculation behind a "sum of points" site function:

    1. find each SPF point's device point, by device name and point name;
    2. read all their readings in the window (one historian query);
    3. at each poll timestamp, take value x scale x sign of every point;
    4. add them up, at each timestamp where every point has a value.

It returns list[TimestampedValue], the same type a stored virtual point's compute returns, so the
one calculation serves both an endpoint and a stored VIRTUAL point:

    # endpoint: computed on request, nothing stored
    values = await spf_common_sum_points(ctx, SITE_ASSETS_ACTIVE_POWER, params.resolve_window())

    # stored: declare SiteVirtualPoint(..., compute=<this>) in the site's profile.py
    async def assets_active_power(ctx: VirtualPointContext) -> list[TimestampedValue]:
        return await spf_common_sum_points(ctx, SITE_ASSETS_ACTIVE_POWER, ctx.window)
"""

from datetime import datetime, timedelta

from schemas.api_models import DevicePointResponse, PointTimeseries, TimeseriesPoint
from schemas.internal_models import TimestampedValue
from schemas.site_profiles import SiteContext, TimeWindow
from site_profiles.common.shared_helper_functions import spf_common_get_point_timeseries
from site_profiles.declarations.spf_point import SpfPoint
from utils.exceptions import NotFoundError


async def spf_common_sum_points(
    ctx: SiteContext, spf_points: tuple[SpfPoint, ...], window: TimeWindow
) -> list[TimestampedValue]:
    """At each poll timestamp in `window`: the sum of value x scale x sign over `spf_points`.
    A timestamp where any point has no value is left out, never part-summed."""
    device_points = [spf_common_find_device_point(ctx, spf_point) for spf_point in spf_points]
    readings = await spf_common_get_point_timeseries(ctx, device_points, window)

    # Every point's scaled, signed value, grouped by poll timestamp.
    values_at: dict[datetime, list[float]] = {}
    for spf_point, device_point in zip(spf_points, device_points, strict=True):
        for sample in readings[device_point.id].timeseries:
            if sample.value is None:
                continue
            timestamp = spf_common_poll_timestamp(sample.time)
            values_at.setdefault(timestamp, []).append(
                sample.value * spf_point.scale * spf_point.sign
            )

    # The sum at each timestamp where every point was read.
    return [
        TimestampedValue(time=timestamp, value=sum(values))
        for timestamp, values in sorted(values_at.items())
        if len(values) == len(spf_points)
    ]


def spf_common_find_device_point(ctx: SiteContext, spf_point: SpfPoint) -> DevicePointResponse:
    """The device point an SPF point names. A missing device or point, or a STANDARDIZED point not
    linked to a real one yet, is a 404 naming it."""
    device = next((device for device in ctx.devices if device.name == spf_point.device), None)
    if device is None:
        raise NotFoundError(f"Site {ctx.site.site_id} has no device '{spf_point.device}'")
    point = next(
        (
            point
            for point in device.points.standardized + device.points.native + device.points.virtual
            if point.name == spf_point.point
        ),
        None,
    )
    if point is None:
        raise NotFoundError(f"Device '{spf_point.device}' has no point '{spf_point.point}'")
    if point in device.points.standardized and point.source_point_id is None:
        raise NotFoundError(
            f"Device '{spf_point.device}': {spf_point.point} isn't linked to a real point yet; link it"
        )
    return point


def spf_common_poll_timestamp(time: datetime) -> datetime:
    """A reading's time rounded to the nearest second. One poll reads every device within a few
    milliseconds, so the readings of one poll share this timestamp."""
    return (time + timedelta(milliseconds=500)).replace(microsecond=0)


def spf_common_points_series(
    values: list[TimestampedValue], name: str, unit: str
) -> PointTimeseries:
    """A computed series to chart (id 0: it's not a stored point)."""
    return PointTimeseries(
        id=0,
        name=name,
        data_type="float32",
        unit=unit,
        point_class="ANALOG",
        count=len(values),
        timeseries=[TimeseriesPoint(time=value.time, value=value.value) for value in values],
    )
