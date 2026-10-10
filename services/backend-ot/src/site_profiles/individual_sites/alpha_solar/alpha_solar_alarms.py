"""
Alpha Solar Farm's alarms in code (PROFILE alarms). Only the ones declared in profile.py exist.
Each check is async (ctx: AlarmContext) -> AlarmCheck and runs every evaluation cycle.

PLACEHOLDER: the alarm here only shows how a profile alarm is written and wired; it is not a real
alarm of the site. Replace it (and its declaration in profile.py) with the site's actual alarms.
"""

from helpers.reads.device_points_readings import get_latest_readings_by_point_ids
from schemas.site_profiles import AlarmCheck, AlarmContext
from site_profiles.individual_sites.alpha_solar.alpha_solar_functions import INVERTER_ONLINE_STATES

INVERTER_STATE_POINT = "inverter_state"


async def placeholder_profile_alarm_1(ctx: AlarmContext) -> AlarmCheck:
    """PLACEHOLDER example check: active while the site's `inverter_state` point is not an online
    state (mppt, derating). Not active when the site has no such point or it has no reading yet."""
    points = ctx.points_named(INVERTER_STATE_POINT)
    if not points:
        return AlarmCheck(active=False)
    point = points[0]
    (reading,) = await get_latest_readings_by_point_ids([point.id], site_id=ctx.site.site_id)
    if reading.derived_value is None:
        return AlarmCheck(active=False, device_id=point.device_id)
    return AlarmCheck(
        active=int(reading.derived_value) not in INVERTER_ONLINE_STATES,
        value=reading.derived_value,
        device_id=point.device_id,
    )
