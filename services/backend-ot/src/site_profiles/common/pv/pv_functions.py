"""
Common PV functions, shared by every site. Historian reads go through
spf_common_get_point_timeseries in common/shared_helper_functions.py; the math is in
common/pv/pv_helper_functions.py.
"""

from schemas.api_models import DevicePointResponse
from schemas.site_profiles import PvPowerSignConvention, PvPowerStats, SiteContext, TimeWindow
from site_profiles.common.pv.pv_helper_functions import spf_common_pv_power_stats_from_samples
from site_profiles.common.shared_helper_functions import spf_common_get_point_timeseries
from utils.exceptions import SiteProfileConfigError


async def spf_common_pv_power_stats(
    ctx: SiteContext,
    power_point: DevicePointResponse,
    window: TimeWindow,
    producing_threshold_kw: float,
    sign_convention: PvPowerSignConvention = "positive_is_production",
) -> PvPowerStats:
    """
    Peak, average and minimum power, and energy produced and consumed, of one PV power point
    over `window`: whole-window figures plus producing-hours ones that leave the night out.

    power_point: the PV AC power point (inverter output or PV meter), in W, kW or MW.
    producing_threshold_kw: power at or above which the plant counts as producing, e.g. 1 % of
        rated power; must be > 0.
    sign_convention: "positive_is_consumption" for a meter that reports production as negative.

    The definitions are in common/pv/pv_helper_functions.py (spf_common_pv_power_stats_from_samples).
    """
    if producing_threshold_kw <= 0:
        raise SiteProfileConfigError(
            f"PV power stats: producing_threshold_kw must be > 0, got {producing_threshold_kw}"
        )
    series_by_point = await spf_common_get_point_timeseries(ctx, [power_point], window)
    try:
        return spf_common_pv_power_stats_from_samples(
            series_by_point[power_point.id].timeseries,
            power_point.unit,
            producing_threshold_kw,
            sign_convention,
        )
    except ValueError as err:  # a point with an unsupported unit
        raise SiteProfileConfigError(
            f"PV power stats: point '{power_point.name}' (id {power_point.id}): {err}"
        ) from err
