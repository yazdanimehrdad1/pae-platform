"""
Device health checks any site profile can declare (or build its own on), for SLD info boxes.

Each is async (ctx: DeviceHealthContext) -> DeviceHealth and judges `ctx.device`.
"""

from helpers.alarms.events import count_active_device_events
from helpers.reads.device_points_readings import get_device_last_reading_time
from schemas.site_profiles import DeviceHealth, DeviceHealthContext


async def common_no_active_fault_alarm(ctx: DeviceHealthContext) -> DeviceHealth:
    """Healthy while the device has no active fault alarm; unknown until it has reported once."""
    device_id = ctx.device.device_id
    if await get_device_last_reading_time(device_id) is None:
        return DeviceHealth(healthy=None, reason="No readings from the device yet")
    faults = await count_active_device_events(device_id, "fault")
    if faults:
        return DeviceHealth(healthy=False, reason=f"{faults} active fault alarm{'s' if faults > 1 else ''}")
    return DeviceHealth(healthy=True)
