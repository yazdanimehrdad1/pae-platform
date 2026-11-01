"""
Powerflow 2BESS 1PV's own controllers: site-wide (site_*). Only the ones declared in profile.py
get an endpoint. Each one reads its SPF points (powerflow_2bess_1pv_points.py) with
spf_common_sum_points (value x scale x sign at each poll timestamp; export positive, import
negative) and computes its result from those series.
"""

from collections import Counter
from datetime import timedelta

from schemas.api_models import PointTimeseries, TimeseriesPoint
from schemas.internal_models import TimestampedValue
from schemas.site_profiles import (
    RoundTripEfficiencySettings,
    SiteContext,
    TimeWindow,
    TimeWindowParams,
)
from schemas.site_profiles.individual_sites.powerflow_2bess_1pv import (
    BessRollingRoundTripEfficiencyResult,
    BessRoundTripEfficiencyResult,
    PowerSeriesResult,
    RollingRoundTripEfficiencyParams,
)
from site_profiles.common.bess.bess_functions import (
    spf_common_bess_rolling_round_trip_efficiency,
    spf_common_bess_round_trip_efficiency,
)
from site_profiles.common.spf_point_functions import spf_common_points_series, spf_common_sum_points
from site_profiles.declarations.spf_point import SpfPoint
from site_profiles.individual_sites.powerflow_2bess_1pv.powerflow_2bess_1pv_points import (
    SITE_ASSETS_ACTIVE_POWER,
    SITE_ASSETS_REACTIVE_POWER,
    SITE_POI_ACTIVE_POWER,
    SITE_POI_REACTIVE_POWER,
    SPF_BESS1_ACTIVE_POWER,
    SPF_BESS1_STATE_OF_CHARGE,
    SPF_BESS2_ACTIVE_POWER,
    SPF_BESS2_STATE_OF_CHARGE,
)

# Both BESSs: 10 MWh each (powerflow's capacity_kwh), power measured on the inverter's AC side.
BESS_ROUND_TRIP_SETTINGS = RoundTripEfficiencySettings(
    usable_energy_kwh=10000.0,
    boundary="ac",
    min_charged_kwh=500.0,  # 5 % of a full charge: less and the ratio is noise
    max_soc_change_pct=20.0,  # a larger SoC change and the correction would dominate
)
# The rolling values' min_charged_kwh: this much a day of lookback (7 days: 3500 kWh).
MIN_CHARGED_KWH_PER_DAY = 500.0


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


async def site_bess1_round_trip_efficiency(
    ctx: SiteContext, params: TimeWindowParams
) -> BessRoundTripEfficiencyResult:
    """BESS 1's round trip efficiency over the window."""
    return await round_trip_efficiency(
        ctx, params, SPF_BESS1_ACTIVE_POWER, SPF_BESS1_STATE_OF_CHARGE
    )


async def site_bess2_round_trip_efficiency(
    ctx: SiteContext, params: TimeWindowParams
) -> BessRoundTripEfficiencyResult:
    """BESS 2's round trip efficiency over the window."""
    return await round_trip_efficiency(
        ctx, params, SPF_BESS2_ACTIVE_POWER, SPF_BESS2_STATE_OF_CHARGE
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


async def round_trip_efficiency(
    ctx: SiteContext, params: TimeWindowParams, power: SpfPoint, soc: SpfPoint
) -> BessRoundTripEfficiencyResult:
    """
    One BESS's round trip efficiency in the requested window: its power (kW, discharge positive)
    and SoC (%) series, read through their SPF points, into spf_common_bess_round_trip_efficiency.
    """
    window = params.resolve_window()
    power_kw: list[TimestampedValue] = await spf_common_sum_points(ctx, (power,), window)
    soc_pct: list[TimestampedValue] = await spf_common_sum_points(ctx, (soc,), window)
    return BessRoundTripEfficiencyResult(
        site_id=ctx.site.site_id,
        start_time=window.display(window.start_time),
        end_time=window.display(window.end_time),
        bess=power.device,
        round_trip=spf_common_bess_round_trip_efficiency(
            power_kw, soc_pct, BESS_ROUND_TRIP_SETTINGS
        ),
    )


async def site_bess1_rolling_round_trip_efficiency(
    ctx: SiteContext, params: RollingRoundTripEfficiencyParams
) -> BessRollingRoundTripEfficiencyResult:
    """BESS 1's round trip efficiency over the window, each value over the last lookback_days."""
    return await rolling_round_trip_efficiency(
        ctx, params, SPF_BESS1_ACTIVE_POWER, SPF_BESS1_STATE_OF_CHARGE
    )


async def site_bess2_rolling_round_trip_efficiency(
    ctx: SiteContext, params: RollingRoundTripEfficiencyParams
) -> BessRollingRoundTripEfficiencyResult:
    """BESS 2's round trip efficiency over the window, each value over the last lookback_days."""
    return await rolling_round_trip_efficiency(
        ctx, params, SPF_BESS2_ACTIVE_POWER, SPF_BESS2_STATE_OF_CHARGE
    )


async def rolling_round_trip_efficiency(
    ctx: SiteContext, params: RollingRoundTripEfficiencyParams, power: SpfPoint, soc: SpfPoint
) -> BessRollingRoundTripEfficiencyResult:
    """
    One BESS's round trip efficiency at every whole step (rolling_step) in the requested window, each over the
    last lookback_days: its power and SoC are read from lookback_days before the window, so the
    first value has a full lookback. min_charged_kwh grows with the lookback
    (MIN_CHARGED_KWH_PER_DAY a day).
    """
    window = params.resolve_window()
    lookback = timedelta(days=params.lookback_days)
    read_window = TimeWindow(
        start_time=window.start_time - lookback,
        end_time=window.end_time,
        display_tz=window.display_tz,
    )
    power_kw = await spf_common_sum_points(ctx, (power,), read_window)
    soc_pct = await spf_common_sum_points(ctx, (soc,), read_window)
    settings = BESS_ROUND_TRIP_SETTINGS.model_copy(
        update={"min_charged_kwh": MIN_CHARGED_KWH_PER_DAY * params.lookback_days}
    )
    step = rolling_step(window)
    rolling = spf_common_bess_rolling_round_trip_efficiency(
        power_kw,
        soc_pct,
        settings,
        start_time=window.start_time,
        end_time=window.end_time,
        lookback=lookback,
        step=step,
    )
    rte_samples = [
        TimeseriesPoint(time=value.time, value=value.round_trip.round_trip_efficiency_pct)
        for value in rolling
    ]
    return BessRollingRoundTripEfficiencyResult(
        site_id=ctx.site.site_id,
        start_time=window.display(window.start_time),
        end_time=window.display(window.end_time),
        bess=power.device,
        lookback_days=params.lookback_days,
        step_minutes=int(step / timedelta(minutes=1)),
        values_by_status=Counter(value.round_trip.status for value in rolling),
        series=PointTimeseries(
            id=0,
            name=f"{power.device} round trip efficiency (%)",
            data_type="float32",
            unit="%",
            point_class="ANALOG",
            count=len(rte_samples),
            timeseries=rte_samples,
        ),
    )


def rolling_step(window: TimeWindow) -> timedelta:
    """The rolling values' spacing, so every range charts as a curve: 1 min up to 1 hour
    (60 values), 15 min under a week (1D: 96), 1 hour for a week or more (1W: 168)."""
    duration = window.end_time - window.start_time
    if duration <= timedelta(hours=1):
        return timedelta(minutes=1)
    if duration < timedelta(days=7):
        return timedelta(minutes=15)
    return timedelta(hours=1)
