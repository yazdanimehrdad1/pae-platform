"""
Alpha Solar Farm's alarms in code (PROFILE alarms). Only the ones declared in profile.py exist.
Each check is async (ctx: AlarmContext) -> AlarmCheck and runs every evaluation cycle.
"""

from helpers.reads.device_points_readings import get_latest_readings_by_point_ids
from helpers.sites.site_health import alarm_points
from helpers.virtual_points.resolve import input_max_gap
from schemas.site_profiles import AlarmCheck, AlarmContext
from site_profiles.individual_sites.alpha_solar.alpha_solar_helper_functions import set_alarm_points


async def high_severity_alarm_point_active(ctx: AlarmContext) -> AlarmCheck:
    """Active while any ALARM-class point of severity HIGH, on any of the site's devices, reads
    non-zero: some device reports a fault. Readings older than input_max_gap() don't count.

    value: how many HIGH points are set. device_id: their device when they are all on one,
    else None (site-level). Not active when the site has no HIGH alarm points (no read then)."""
    points = [point for device in ctx.devices for point in alarm_points(device, ["HIGH"])]
    if not points:
        return AlarmCheck(active=False)
    readings = await get_latest_readings_by_point_ids([point.id for point in points], site_id=ctx.site.site_id)
    set_points = set_alarm_points(points, readings, ctx.now - input_max_gap())
    devices = {point.device_id for point in set_points}
    return AlarmCheck(
        active=bool(set_points),
        value=len(set_points),
        device_id=devices.pop() if len(devices) == 1 else None,
    )
