"""
Powerflow 2BESS 1PV's own controllers: site-wide (site_*). Only the ones declared in profile.py
get an endpoint. Each one sums its SPF points (powerflow_2bess_1pv_points.py) at each poll
timestamp with spf_common_sum_points; export positive, import negative.
"""

from schemas.site_profiles import SiteContext, TimeWindowParams
from schemas.site_profiles.individual_sites.powerflow_2bess_1pv import PowerSeriesResult
from site_profiles.common.spf_point_functions import spf_common_points_series, spf_common_sum_points
from site_profiles.declarations.spf_point import SpfPoint
from site_profiles.individual_sites.powerflow_2bess_1pv.powerflow_2bess_1pv_points import (
    SITE_ASSETS_ACTIVE_POWER,
    SITE_ASSETS_REACTIVE_POWER,
    SITE_POI_ACTIVE_POWER,
    SITE_POI_REACTIVE_POWER,
)


async def site_poi_active_power(ctx: SiteContext, params: TimeWindowParams) -> PowerSeriesResult:
    """The POI meter's active power (kW)."""
    return await power_series(ctx, params, SITE_POI_ACTIVE_POWER, "POI active power", "kW")


async def site_poi_reactive_power(ctx: SiteContext, params: TimeWindowParams) -> PowerSeriesResult:
    """The POI meter's reactive power (kvar)."""
    return await power_series(ctx, params, SITE_POI_REACTIVE_POWER, "POI reactive power", "kvar")


async def site_assets_active_power(ctx: SiteContext, params: TimeWindowParams) -> PowerSeriesResult:
    """BESS 1 + BESS 2 + PV 1 active power (kW)."""
    return await power_series(ctx, params, SITE_ASSETS_ACTIVE_POWER, "assets active power", "kW")


async def site_assets_reactive_power(
    ctx: SiteContext, params: TimeWindowParams
) -> PowerSeriesResult:
    """BESS 1 + BESS 2 + PV 1 reactive power (kvar)."""
    return await power_series(
        ctx, params, SITE_ASSETS_REACTIVE_POWER, "assets reactive power", "kvar"
    )


async def power_series(
    ctx: SiteContext,
    params: TimeWindowParams,
    spf_points: tuple[SpfPoint, ...],
    name: str,
    unit: str,
) -> PowerSeriesResult:
    """The SPF points summed at each poll timestamp in the requested window, with peak and average."""
    window = params.resolve_window()
    values = await spf_common_sum_points(ctx, spf_points, window)
    numbers = [value.value for value in values]
    return PowerSeriesResult(
        site_id=ctx.site.site_id,
        start_time=window.display(window.start_time),
        end_time=window.display(window.end_time),
        unit=unit,
        peak=max(numbers) if numbers else None,
        average=sum(numbers) / len(numbers) if numbers else None,
        series=spf_common_points_series(values, f"{name} ({unit})", unit),
    )
