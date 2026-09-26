"""
Common controllers: shared by every site. A site exposes one by declaring a
SiteEndpoint(kind="common", ...) for it in its own profile.py.
"""

from schemas.site_profiles import (
    DeviceEnergy,
    EnergySummaryResult,
    SiteContext,
    TimeWindowParams,
)
from site_profiles.common.calculations import energy_kwh
from site_profiles.common.historian import get_point_series
from utils.exceptions import SiteProfileConfigError

POWER_POINT_NAME = "active_power"


async def common_energy_summary(ctx: SiteContext, params: TimeWindowParams) -> EnergySummaryResult:
    """
    SAMPLE (common): energy produced in the window, per device and in total.

    Integrates the `active_power` point of every device that has one.
    """
    window = params.resolve_window()
    points = ctx.points_named(POWER_POINT_NAME)
    series_by_point = await get_point_series(ctx, points, window)
    device_names = {device.device_id: device.name for device in ctx.devices}

    devices: list[DeviceEnergy] = []
    for point in points:
        series = series_by_point[point.id]
        try:
            device_energy_kwh = energy_kwh(series.timeseries, point.unit)
        except ValueError as err:
            raise SiteProfileConfigError(
                f"Point '{point.name}' (id {point.id}) can't be integrated: {err}"
            ) from err
        devices.append(
            DeviceEnergy(
                device_id=point.device_id,
                device_name=device_names[point.device_id],
                point_id=point.id,
                sample_count=series.count,
                energy_kwh=device_energy_kwh,
            )
        )
    return EnergySummaryResult(
        site_id=ctx.site.site_id,
        start_time=window.display(window.start_time),
        end_time=window.display(window.end_time),
        energy_kwh=sum(device.energy_kwh for device in devices),
        devices=devices,
    )
