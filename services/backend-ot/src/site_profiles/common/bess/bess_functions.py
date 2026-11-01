"""
Common BESS functions, shared by every site. A site calls them from its own controllers, alarms
or health checks, passing the points it found in its SiteContext. Historian reads go through
spf_common_get_point_timeseries in common/shared_helper_functions.py.
"""

from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta

from helpers.sampling.alignment import default_max_gap
from schemas.api_models import DevicePointResponse, PointTimeseries, TimeseriesPoint
from schemas.internal_models import TimestampedValue
from schemas.site_profiles import (
    DeviceEnergy,
    EnergySeriesResult,
    EnergySummaryResult,
    PhaseImbalanceTimeseries,
    RoundTripEfficiencyAtTime,
    RoundTripEfficiencyResult,
    RoundTripEfficiencySettings,
    SiteContext,
    TimeWindow,
)
from site_profiles.common.bess.bess_helper_functions import (
    spf_common_check_phase_points,
    spf_common_phase_imbalance_timeseries,
    spf_common_round_trip_efficiency_result,
)
from site_profiles.common.shared_helper_functions import (
    spf_common_aligned_times,
    spf_common_combine_series,
    spf_common_cumulative_energy_kwh,
    spf_common_cumulative_power_by_sign_kwh,
    spf_common_get_point_timeseries,
    spf_common_integrate_power_to_energy_kwh,
    spf_common_split_power_by_sign_kwh,
)
from utils.exceptions import SiteProfileConfigError


def _spf_common_power_point_device_names(
    ctx: SiteContext, power_points: list[DevicePointResponse]
) -> dict[int, str]:
    """Device name by id for the site; a power point on a device outside it is a config error."""
    device_names = {device.device_id: device.name for device in ctx.devices}
    unknown = [point for point in power_points if point.device_id not in device_names]
    if unknown:
        raise SiteProfileConfigError(
            "energy by device: points on devices outside the site: "
            + ", ".join(f"'{point.name}' (id {point.id})" for point in unknown)
        )
    return device_names


async def spf_common_energy_kwh_by_device(
    ctx: SiteContext, power_points: list[DevicePointResponse], window: TimeWindow
) -> EnergySummaryResult:
    """
    Energy in `window` per device and in total, integrated from the given power points.

    power_points: one power point per device (W, kW or MW), e.g. the ones a site controller
        found with ctx.points_named(...). Each gives one entry in `devices`; none gives 0 kWh.
    A point with a non-power unit, or on a device not in ctx.devices, is a SiteProfileConfigError.
    """
    device_names = _spf_common_power_point_device_names(ctx, power_points)
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


def spf_common_bess_round_trip_efficiency(
    power_kw: list[TimestampedValue],
    soc_pct: list[TimestampedValue],
    settings: RoundTripEfficiencySettings,
) -> RoundTripEfficiencyResult:
    """
    Round trip efficiency of one BESS, from series its site already read and sanitized.

    power_kw: the BESS's power in kW, export (discharge) positive, charge negative
        (value x scale x sign, e.g. from spf_common_sum_points with the site's SPF point).
    soc_pct: its state of charge in %, the same way; only the first and last values are used.
    settings: the BESS's usable energy, the measurement boundary and the trust limits.

        E_dis = integral of max(P, 0) dt            E_ch = integral of max(-P, 0) dt
        Delta S = (SoC end - SoC start) / 100 * usable_energy_kwh
        x = (Delta S + sqrt(Delta S^2 + 4 * E_ch * E_dis)) / (2 * E_ch)        eta_RT = x^2

    With Delta S = 0 (SoC ended where it started) eta_RT is E_dis / E_ch. The derivation and
    the status rules are in common/bess/bess_helper_functions.py
    (_spf_common_round_trip_efficiency, spf_common_round_trip_efficiency_result).
    """
    power_samples = [TimeseriesPoint(time=value.time, value=value.value) for value in power_kw]
    discharged_kwh, charged_kwh = spf_common_split_power_by_sign_kwh(power_samples, "kW")
    soc_samples = [TimeseriesPoint(time=value.time, value=value.value) for value in soc_pct]
    return spf_common_round_trip_efficiency_result(
        charged_kwh=charged_kwh,
        discharged_kwh=discharged_kwh,
        soc_samples=soc_samples,
        settings=settings,
    )


def spf_common_bess_rolling_round_trip_efficiency(
    power_kw: list[TimestampedValue],
    soc_pct: list[TimestampedValue],
    settings: RoundTripEfficiencySettings,
    *,
    start_time: datetime,
    end_time: datetime,
    lookback: timedelta,
    step: timedelta,
) -> list[RoundTripEfficiencyAtTime]:
    """
    Round trip efficiency at every whole step (e.g. every hour on the hour) from start_time to
    end_time, each over the `lookback` ending there: the same result
    spf_common_bess_round_trip_efficiency gives for the window [time - lookback, time].

    power_kw and soc_pct are as for spf_common_bess_round_trip_efficiency, but must reach back
    to start_time - lookback, or the first values see less than `lookback` of data. Charged
    and discharged energy are running totals taken once (spf_common_cumulative_power_by_sign_kwh),
    so each value is a difference of two totals plus two SoC lookups, not a new integration.
    Values are on a fixed grid, not at the readings' own times: each one is a window's result.
    """
    power_samples = [TimeseriesPoint(time=value.time, value=value.value) for value in power_kw]
    cumulative = spf_common_cumulative_power_by_sign_kwh(power_samples, "kW")
    power_times = [time for time, _, _ in cumulative]
    soc_readings = sorted((value.time, value.value) for value in soc_pct)
    soc_times = [time for time, _ in soc_readings]

    results: list[RoundTripEfficiencyAtTime] = []
    for time in spf_common_aligned_times(start_time, end_time, step):
        window_start = time - lookback

        # Energy between the window's first and last power readings (none: 0 kWh).
        first = bisect_left(power_times, window_start)
        last = bisect_right(power_times, time) - 1
        discharged_kwh, charged_kwh = 0.0, 0.0
        if last > first:
            discharged_kwh = cumulative[last][1] - cumulative[first][1]
            charged_kwh = cumulative[last][2] - cumulative[first][2]

        # The window's first and last SoC readings (fewer than two: missing_soc_data).
        first = bisect_left(soc_times, window_start)
        last = bisect_right(soc_times, time) - 1
        soc_samples = (
            [TimeseriesPoint(time=soc_times[index], value=soc_readings[index][1]) for index in (first, last)]
            if last > first
            else []
        )
        results.append(
            RoundTripEfficiencyAtTime(
                time=time,
                round_trip=spf_common_round_trip_efficiency_result(
                    charged_kwh=charged_kwh,
                    discharged_kwh=discharged_kwh,
                    soc_samples=soc_samples,
                    settings=settings,
                ),
            )
        )
    return results


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


async def spf_common_energy_kwh_series_by_device(
    ctx: SiteContext,
    power_points: list[DevicePointResponse],
    window: TimeWindow,
) -> EnergySeriesResult:
    """
    Cumulative energy over `window`, per device and for the site, from the given power points
    (one per device, as for spf_common_energy_kwh_by_device), at the points' own sample times.
    The site total is the devices' cumulative energy summed per poll cycle
    (spf_common_combine_series); while a device has no recent sample the total has a gap.
    """
    device_names = _spf_common_power_point_device_names(ctx, power_points)
    series_by_point = await spf_common_get_point_timeseries(ctx, power_points, window)

    device_series: list[PointTimeseries] = []
    for point in power_points:
        try:
            cumulative = spf_common_cumulative_energy_kwh(series_by_point[point.id].timeseries, point.unit)
        except ValueError as err:
            raise SiteProfileConfigError(
                f"Point '{point.name}' (id {point.id}) can't be integrated: {err}"
            ) from err
        device_series.append(
            _spf_common_energy_series(point.id, f"{device_names[point.device_id]} energy", cumulative)
        )
    site_total = spf_common_combine_series(
        [series.timeseries for series in device_series], sum, default_max_gap()
    )
    return EnergySeriesResult(
        site_id=ctx.site.site_id,
        start_time=window.display(window.start_time),
        end_time=window.display(window.end_time),
        energy_kwh=sum(series.timeseries[-1].value or 0.0 for series in device_series if series.timeseries),
        series=[_spf_common_energy_series(0, "site energy", site_total), *device_series],
    )


def _spf_common_energy_series(
    series_id: int, name: str, samples: list[TimeseriesPoint]
) -> PointTimeseries:
    return PointTimeseries(
        id=series_id,
        name=name,
        data_type="float32",
        unit="kWh",
        point_class="ANALOG",
        count=len(samples),
        timeseries=samples,
    )
