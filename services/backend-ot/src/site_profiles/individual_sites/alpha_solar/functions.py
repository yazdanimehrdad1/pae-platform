"""
Alpha Solar Farm's own controllers: site-wide (site_*) and per-device (device_*).
Only the ones declared in profile.py get an endpoint.
"""

from schemas.site_profiles import SiteContext, TimeWindowParams
from schemas.site_profiles.individual_sites.alpha_solar import (
    InverterAvailabilityResult,
    PoiPowerResult,
)
from site_profiles.common.calculations import average, power_to_kw_factor
from site_profiles.common.historian import get_point_series
from site_profiles.individual_sites.alpha_solar.calculations import (
    availability_pct,
    count_online_samples,
)
from site_profiles.individual_sites.alpha_solar.historian import get_poi_active_power
from utils.exceptions import InternalError, NotFoundError, SiteProfileConfigError

INVERTER_STATE_POINTS = ("inverter_state",)
INVERTER_ONLINE_STATES = frozenset({3, 4})  # mppt, derating

PLANT_INVERTER_MODE_POINTS = ("inv01_mode", "inv02_mode", "inv03_mode", "inv04_mode")
PLANT_INVERTER_ONLINE_MODES = frozenset({1, 2})  # derate, running


async def site_poi_power(ctx: SiteContext, params: TimeWindowParams) -> PoiPowerResult:
    """SAMPLE (site, time-based result): POI active power series with peak and average."""
    window = params.resolve_window()
    series = await get_poi_active_power(ctx, window)
    try:
        factor = power_to_kw_factor(series.unit)
    except ValueError as err:
        raise SiteProfileConfigError(f"Point '{series.name}': {err}") from err
    values_kw = [sample.value * factor for sample in series.timeseries if sample.value is not None]
    mean = average(series.timeseries)
    return PoiPowerResult(
        site_id=ctx.site.site_id,
        start_time=window.display(window.start_time),
        end_time=window.display(window.end_time),
        peak_kw=max(values_kw) if values_kw else None,
        average_kw=mean * factor if mean is not None else None,
        series=series,
    )


async def device_inverter_availability(
    ctx: SiteContext, params: TimeWindowParams
) -> InverterAvailabilityResult:
    """SAMPLE (device, single-value result): availability from the PV inverter's `inverter_state`."""
    return await _state_availability(ctx, params, INVERTER_STATE_POINTS, INVERTER_ONLINE_STATES)


async def device_plant_inverter_availability(
    ctx: SiteContext, params: TimeWindowParams
) -> InverterAvailabilityResult:
    """
    SAMPLE (device, sharing code with another controller): the PV plant controller
    (device_3) reports four inverters as `inv01_mode`..`inv04_mode`, so availability is
    pooled across all four.
    """
    return await _state_availability(
        ctx, params, PLANT_INVERTER_MODE_POINTS, PLANT_INVERTER_ONLINE_MODES
    )


async def _state_availability(
    ctx: SiteContext,
    params: TimeWindowParams,
    state_points: tuple[str, ...],
    online_states: frozenset[int],
) -> InverterAvailabilityResult:
    """Share of samples, across `state_points` of the target device, that hold an online code."""
    device = ctx.device
    if device is None:
        raise InternalError("A device controller was called without a device")
    window = params.resolve_window()

    points = [
        point
        for point_name in state_points
        for point in ctx.points_named(point_name, [device])
    ]
    found_names = {point.name for point in points}
    missing = [name for name in state_points if name not in found_names]
    if missing:
        raise NotFoundError(
            f"Device '{device.name}' (id {device.device_id}) has no state point(s) {missing}"
        )

    series_by_point = await get_point_series(ctx, points, window)
    samples = [sample for series in series_by_point.values() for sample in series.timeseries]
    online = count_online_samples(samples, online_states)
    return InverterAvailabilityResult(
        site_id=ctx.site.site_id,
        device_id=device.device_id,
        device_name=device.name,
        start_time=window.display(window.start_time),
        end_time=window.display(window.end_time),
        state_points=list(state_points),
        online_states=sorted(online_states),
        sample_count=len(samples),
        online_sample_count=online,
        availability_pct=availability_pct(online, len(samples)),
    )
