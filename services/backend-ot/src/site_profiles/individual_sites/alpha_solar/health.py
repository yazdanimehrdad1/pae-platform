"""
Alpha Solar Farm's device health checks (declared in profile.py). Each is async
(ctx: DeviceHealthContext) -> DeviceHealth and judges `ctx.device`.
"""

from helpers.reads.calculate_reads import translate_enum_value
from helpers.reads.device_points_readings import get_latest_readings_by_point_ids
from schemas.site_profiles import DeviceHealth, DeviceHealthContext
from site_profiles.common.health import common_no_active_fault_alarm

# The BESS state points whose 'fault' state makes it unhealthy.
BESS_STATE_POINTS = ("battery_state", "bms_state")
FAULT_STATE = "fault"


async def bess_health(ctx: DeviceHealthContext) -> DeviceHealth:
    """The common check (no active fault alarm), and neither battery_state nor bms_state reads fault."""
    verdict = await common_no_active_fault_alarm(ctx)
    if verdict.healthy is not True:
        return verdict
    points = [point for name in BESS_STATE_POINTS for point in ctx.points_named(name, [ctx.device])]
    if not points:
        return verdict
    readings = await get_latest_readings_by_point_ids(
        [point.id for point in points], site_id=ctx.site.site_id
    )
    for reading in readings:
        if reading.derived_value is None or not reading.enum_detail:
            continue
        label = translate_enum_value(reading.derived_value, reading.enum_detail)
        if label is not None and label.lower() == FAULT_STATE:
            return DeviceHealth(healthy=False, reason=f"{reading.name} is {FAULT_STATE}")
    return verdict
