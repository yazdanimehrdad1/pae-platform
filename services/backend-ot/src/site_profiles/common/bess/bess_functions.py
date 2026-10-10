"""
Common BESS functions, shared by every site. A site calls them from its own controllers, alarms
or health checks, passing the points it found in its SiteContext. Historian reads go through
spf_common_get_point_timeseries in common/shared_helper_functions.py.
"""

from schemas.api_models import DevicePointResponse
from schemas.site_profiles import (
    DeviceEnergy,
    EnergySummaryResult,
    PhaseImbalanceTimeseries,
    RoundTripCounterSource,
    RoundTripEfficiencyResult,
    RoundTripEfficiencySettings,
    RoundTripPowerSource,
    SiteContext,
    TimeWindow,
)
from site_profiles.common.bess.bess_helper_functions import (
    spf_common_check_phase_points,
    spf_common_phase_imbalance_timeseries,
    spf_common_round_trip_efficiency_result,
)
from site_profiles.common.shared_helper_functions import (
    spf_common_counter_energy_kwh,
    spf_common_get_point_timeseries,
    spf_common_integrate_power_to_energy_kwh,
    spf_common_split_power_by_sign_kwh,
)
from utils.exceptions import SiteProfileConfigError


async def spf_common_energy_kwh_by_device(
    ctx: SiteContext, power_points: list[DevicePointResponse], window: TimeWindow
) -> EnergySummaryResult:
    """
    Energy in `window` per device and in total, integrated from the given power points.

    power_points: one power point per device (W, kW or MW), e.g. the ones a site controller
        found with ctx.points_named(...). Each gives one entry in `devices`; none gives 0 kWh.
    A point with a non-power unit, or on a device not in ctx.devices, is a SiteProfileConfigError.
    """
    device_names = {device.device_id: device.name for device in ctx.devices}
    unknown = [point for point in power_points if point.device_id not in device_names]
    if unknown:
        raise SiteProfileConfigError(
            "energy by device: points on devices outside the site: "
            + ", ".join(f"'{point.name}' (id {point.id})" for point in unknown)
        )
    series_by_point = await spf_common_get_point_timeseries(ctx, power_points, window)

    devices: list[DeviceEnergy] = []
    for point in power_points:
        series = series_by_point[point.id]
        try:
            device_energy_kwh = spf_common_integrate_power_to_energy_kwh(
                series.timeseries, point.unit
            )
        except ValueError as err:
            raise SiteProfileConfigError(
                f"Point '{point.name}' (id {point.id}) can't be integrated: {err}"
            ) from err
        devices.append(
            DeviceEnergy(
                device_id=point.device_id,
                device_name=device_names[point.device_id],
                point_id=point.id,
                sample_count=series.count,
                energy_kwh=device_energy_kwh,
            )
        )
    return EnergySummaryResult(
        site_id=ctx.site.site_id,
        start_time=window.display(window.start_time),
        end_time=window.display(window.end_time),
        energy_kwh=sum(device.energy_kwh for device in devices),
        devices=devices,
    )


async def spf_common_bess_round_trip_efficiency(
    ctx: SiteContext,
    energy_source: RoundTripPowerSource | RoundTripCounterSource,
    soc_point: DevicePointResponse,
    window: TimeWindow,
    settings: RoundTripEfficiencySettings,
    aux_counter_point: DevicePointResponse | None = None,
) -> RoundTripEfficiencyResult:
    """
    Round trip efficiency of one BESS over `window`, corrected for the change in stored energy.

    energy_source: one net power point (split by sign) or a charged/discharged counter pair,
        measured at settings.boundary.
    soc_point: state of charge in %; its first and last readings give the SoC change.
    aux_counter_point: auxiliary energy counter (HVAC, controls), only for boundary "system",
        when the auxiliaries are fed outside the measured energy.

    The formula and the status rules are in common/bess/bess_helper_functions.py
    (_spf_common_round_trip_efficiency, spf_common_round_trip_efficiency_result).
    """
    if aux_counter_point is not None and settings.boundary != "system":
        raise SiteProfileConfigError(
            "round trip efficiency: an aux counter only applies to boundary 'system', "
            f"not '{settings.boundary}'"
        )
    if isinstance(energy_source, RoundTripPowerSource):
        energy_points = [energy_source.power_point]
    else:
        energy_points = [
            energy_source.charged_counter_point,
            energy_source.discharged_counter_point,
        ]
    points = [*energy_points, soc_point, *([aux_counter_point] if aux_counter_point else [])]
    if len({point.id for point in points}) != len(points):
        raise SiteProfileConfigError(
            "round trip efficiency: each point may be used once, got "
            + ", ".join(f"'{point.name}' (id {point.id})" for point in points)
        )

    series_by_point = await spf_common_get_point_timeseries(ctx, points, window)
    try:
        if isinstance(energy_source, RoundTripPowerSource):
            power_point = energy_source.power_point
            positive_kwh, negative_kwh = spf_common_split_power_by_sign_kwh(
                series_by_point[power_point.id].timeseries, power_point.unit
            )
            if energy_source.sign_convention == "positive_is_discharge":
                discharged_kwh, charged_kwh = positive_kwh, negative_kwh
            else:
                charged_kwh, discharged_kwh = positive_kwh, negative_kwh
        else:
            charged_point = energy_source.charged_counter_point
            discharged_point = energy_source.discharged_counter_point
            charged_kwh = spf_common_counter_energy_kwh(
                series_by_point[charged_point.id].timeseries,
                charged_point.unit,
                energy_source.counter_rollover,
            )
            discharged_kwh = spf_common_counter_energy_kwh(
                series_by_point[discharged_point.id].timeseries,
                discharged_point.unit,
                energy_source.counter_rollover,
            )
        aux_kwh = (
            None
            if aux_counter_point is None
            else spf_common_counter_energy_kwh(
                series_by_point[aux_counter_point.id].timeseries, aux_counter_point.unit, None
            )
        )
    except ValueError as err:  # a point with an unsupported unit
        raise SiteProfileConfigError(f"round trip efficiency: {err}") from err

    return spf_common_round_trip_efficiency_result(
        boundary=settings.boundary,
        energy_source=energy_source.kind,
        charged_kwh=charged_kwh,
        discharged_kwh=discharged_kwh,
        aux_kwh=aux_kwh,
        soc_samples=series_by_point[soc_point.id].timeseries,
        settings=settings,
    )


async def spf_common_voltage_imbalance_timeseries(
    ctx: SiteContext,
    phase_points: tuple[DevicePointResponse, DevicePointResponse, DevicePointResponse],
    window: TimeWindow,
    min_mean: float,
) -> PhaseImbalanceTimeseries:
    """
    Voltage imbalance (NEMA %) at every timestamp in `window`, from one device's phase A, B
    and C voltage points (L-N or L-L, all three alike). min_mean is in the points' unit, e.g.
    a fraction of nominal: below it the bus is treated as dead and gets no %.
    """
    spf_common_check_phase_points("voltage", phase_points, min_mean)
    series_by_point = await spf_common_get_point_timeseries(ctx, list(phase_points), window)
    return spf_common_phase_imbalance_timeseries(
        "voltage", phase_points, series_by_point, min_mean
    )


async def spf_common_current_imbalance_timeseries(
    ctx: SiteContext,
    phase_points: tuple[DevicePointResponse, DevicePointResponse, DevicePointResponse],
    window: TimeWindow,
    min_mean: float,
) -> PhaseImbalanceTimeseries:
    """
    Current imbalance (NEMA %) at every timestamp in `window`, from one device's phase A, B
    and C current points. min_mean is in the points' unit: below it (no or light load) the %
    would be noise, so the sample gets none.
    """
    spf_common_check_phase_points("current", phase_points, min_mean)
    series_by_point = await spf_common_get_point_timeseries(ctx, list(phase_points), window)
    return spf_common_phase_imbalance_timeseries(
        "current", phase_points, series_by_point, min_mean
    )


async def spf_common_power_imbalance_timeseries(
    ctx: SiteContext,
    phase_points: tuple[DevicePointResponse, DevicePointResponse, DevicePointResponse],
    window: TimeWindow,
    min_mean: float,
) -> PhaseImbalanceTimeseries:
    """
    Active power imbalance (NEMA % of |mean|) at every timestamp in `window`, from one device's
    phase A, B and C power points; signed power is fine. min_mean is in the points' unit:
    below it (e.g. an idle BESS) the % would be noise, so the sample gets none, but its
    spread still shows how far apart the phases are.
    """
    spf_common_check_phase_points("power", phase_points, min_mean)
    series_by_point = await spf_common_get_point_timeseries(ctx, list(phase_points), window)
    return spf_common_phase_imbalance_timeseries(
        "power", phase_points, series_by_point, min_mean
    )


# - BESS calculated aux load

# PV (Photovoltaic)
# 1- Peak power for PV
# 2- Energy consumption for PV
# 3- Average power for PV
# 4- Maximum power for PV
# 5- Minimum power for PV


# Load
# 1- Peak power for loads
# 2- Energy consumption for loads
# 3- Peak demand for loads
# 4- Average power for loads
# 5- Maximum power for loads
# 6- Minimum power for loads
# 7- Total energy for loads
# 8- Average energy for loads
# 9- Maximum energy for loads
# 10- Minimum energy for loads
