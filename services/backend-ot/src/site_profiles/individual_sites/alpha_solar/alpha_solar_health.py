"""
Alpha Solar Farm's device health checks (declared in profile.py). Each is async
(ctx: DeviceHealthContext) -> DeviceHealth and judges `ctx.device`.
"""

from helpers.reads.calculate_reads import translate_enum_value
from helpers.reads.device_points_readings import get_latest_readings_by_point_ids
from schemas.site_profiles import DeviceHealth, DeviceHealthContext

# The BESS state points whose 'fault' state makes it unhealthy.
BESS_STATE_POINTS = ("battery_state", "bms_state")
FAULT_STATE = "fault"


async def bess_health(ctx: DeviceHealthContext) -> DeviceHealth:
    """
    Unhealthy if battery_state or bms_state reads fault (any case), healthy if read and neither
    does, unknown while neither point exists or has a readable value.
    """
    unknown = DeviceHealth(healthy=None, reason="No battery_state or bms_state reading yet")
    points = [point for name in BESS_STATE_POINTS for point in ctx.points_named(name, [ctx.device])]
    if not points:
        return unknown
    readings = await get_latest_readings_by_point_ids(
        [point.id for point in points], site_id=ctx.site.site_id
    )
    read_any = False
    for reading in readings:
        if reading.derived_value is None or not reading.enum_detail:
            continue
        read_any = True
        label = translate_enum_value(reading.derived_value, reading.enum_detail)
        if label is not None and label.lower() == FAULT_STATE:
            return DeviceHealth(healthy=False, reason=f"{reading.name} is {FAULT_STATE}")
    return DeviceHealth(healthy=True) if read_any else unknown
