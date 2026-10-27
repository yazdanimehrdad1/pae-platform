"""
Alpha Solar Farm's stored virtual points. Only the ones declared in profile.py exist. Each compute
function is async (ctx: VirtualPointContext) -> list[TimestampedValue] and runs every poll interval
for the window after the last one stored; it returns one value per input poll in the window.
"""

from schemas.internal_models import TimestampedValue
from schemas.site_profiles import VirtualPointContext
from site_profiles.common.shared_helper_functions import spf_common_get_point_timeseries
from site_profiles.individual_sites.alpha_solar.alpha_solar_helper_functions import (
    POI_ACTIVE_POWER_POINT,
    POI_REACTIVE_POWER_POINT,
    apparent_power_samples,
)
from utils.exceptions import NotFoundError


async def poi_apparent_power(ctx: VirtualPointContext) -> list[TimestampedValue]:
    """POI apparent power (kVA), from the POI active and reactive power on the point's device."""
    names = (POI_ACTIVE_POWER_POINT, POI_REACTIVE_POWER_POINT)
    active, reactive = (next(iter(ctx.points_named(name, [ctx.device])), None) for name in names)
    if active is None or reactive is None:
        raise NotFoundError(f"Device '{ctx.device.name}' needs the points {list(names)}")
    series = await spf_common_get_point_timeseries(ctx, [active, reactive], ctx.window)
    return apparent_power_samples(series[active.id], series[reactive.id])
