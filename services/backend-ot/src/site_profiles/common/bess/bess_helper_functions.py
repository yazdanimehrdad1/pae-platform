"""
BESS helper functions behind common/bess/bess_functions.py. Pure: no DB, no network, no clock.

Naming: spf_common_<name> is called from outside this file (bess_functions.py or a site
package); _spf_common_<name> is only called inside it. Helpers every device type uses live in
common/shared_helper_functions.py.
"""

import math
from datetime import datetime
from typing import Literal

from schemas.api_models import DevicePointResponse, PointTimeseries, TimeseriesPoint
from schemas.site_profiles import (
    BessPowerSignConvention,
    BessPowerStats,
    PhaseImbalanceSample,
    PhaseImbalanceTimeseries,
    PhaseQuantity,
    RoundTripBoundary,
    RoundTripEfficiencyResult,
    RoundTripEfficiencySettings,
)
from site_profiles.common.shared_helper_functions import (
    spf_common_integrate_power_to_energy_kwh,
    spf_common_power_unit_to_kw_factor,
)
from utils.exceptions import SiteProfileConfigError


def spf_common_bess_power_stats_kw(
    samples: list[TimeseriesPoint],
    unit: str | None,
    sign_convention: BessPowerSignConvention = "positive_is_discharge",
) -> BessPowerStats:
    """
    Peak, average, maximum and minimum power of one BESS, in kW, as + discharge / - charge.

    Pass sign_convention="positive_is_charge" for a device that reports charging as positive;
    its values are flipped first. Samples may be in any order; null values are skipped, and
    with none left every statistic is None. average_kw is time-weighted (net energy / covered
    duration) so uneven polling does not skew it; with one sample, or all at one instant, it
    is the plain mean. It shares the PLACEHOLDER gap rule of
    spf_common_integrate_power_to_energy_kwh.
    """
    factor = spf_common_power_unit_to_kw_factor(unit)
    sign = 1.0 if sign_convention == "positive_is_discharge" else -1.0
    readings: list[tuple[datetime, float]] = sorted(
        (sample.time, sample.value * sign) for sample in samples if sample.value is not None
    )
    if not readings:
        return BessPowerStats(
            sample_count=0, peak_kw=None, average_kw=None, max_kw=None, min_kw=None
        )

    values_kw = [value * factor for _, value in readings]
    covered_hours = (readings[-1][0] - readings[0][0]).total_seconds() / 3600
    if covered_hours > 0:
        discharge_positive = [TimeseriesPoint(time=time, value=value) for time, value in readings]
        energy_kwh = spf_common_integrate_power_to_energy_kwh(discharge_positive, unit)
        average_kw = energy_kwh / covered_hours
    else:
        average_kw = sum(values_kw) / len(values_kw)
    max_kw = max(values_kw)
    min_kw = min(values_kw)
    return BessPowerStats(
        sample_count=len(values_kw),
        peak_kw=max(abs(max_kw), abs(min_kw)),
        average_kw=average_kw,
        max_kw=max_kw,
        min_kw=min_kw,
    )


def _spf_common_phase_imbalance_pct(
    phase_a: float, phase_b: float, phase_c: float, min_mean: float
) -> float | None:
    """
    Three-phase imbalance in %, NEMA MG-1: max |phase - mean| / |mean| * 100.

    None when |mean| < min_mean (same unit as the phases): near zero the % is noise, and an
    all-zero (dead) bus has no imbalance to report. One lost phase keeps the mean up, so it
    still reads high (230/230/0 V is 100 %). |mean| makes it work for signed power too.
    """
    if min_mean <= 0:
        raise ValueError(f"min_mean must be > 0, got {min_mean}")
    phases = (phase_a, phase_b, phase_c)
    mean = sum(phases) / 3
    if abs(mean) < min_mean:
        return None
    return max(abs(phase - mean) for phase in phases) / abs(mean) * 100


def _spf_common_phase_imbalance_samples(
    phase_a_samples: list[TimeseriesPoint],
    phase_b_samples: list[TimeseriesPoint],
    phase_c_samples: list[TimeseriesPoint],
    min_mean: float,
) -> list[PhaseImbalanceSample]:
    """
    The imbalance at every timestamp all three phases have a non-null value, oldest first.

    Phases are matched on exact timestamps: the poller stamps every point of a device read in
    one cycle with the same time. A timestamp missing from any phase is skipped.
    """
    phase_b_by_time = {
        sample.time: sample.value for sample in phase_b_samples if sample.value is not None
    }
    phase_c_by_time = {
        sample.time: sample.value for sample in phase_c_samples if sample.value is not None
    }
    imbalance_samples: list[PhaseImbalanceSample] = []
    for sample in sorted(phase_a_samples, key=lambda phase_a_sample: phase_a_sample.time):
        phase_b = phase_b_by_time.get(sample.time)
        phase_c = phase_c_by_time.get(sample.time)
        if sample.value is None or phase_b is None or phase_c is None:
            continue
        phases = (sample.value, phase_b, phase_c)
        imbalance_pct = _spf_common_phase_imbalance_pct(*phases, min_mean)
        imbalance_samples.append(
            PhaseImbalanceSample(
                time=sample.time,
                phase_a=sample.value,
                phase_b=phase_b,
                phase_c=phase_c,
                mean=sum(phases) / 3,
                spread=max(phases) - min(phases),
                imbalance_pct=imbalance_pct,
                status="below_threshold" if imbalance_pct is None else "ok",
            )
        )
    return imbalance_samples


def spf_common_check_phase_points(
    quantity: PhaseQuantity,
    phase_points: tuple[DevicePointResponse, DevicePointResponse, DevicePointResponse],
    min_mean: float,
) -> None:
    """
    Reject a misdeclared imbalance call before anything is read (SiteProfileConfigError).

    The points must be three different points on one device (so their timestamps line up)
    with one unit, and min_mean must be > 0.
    """
    point_names = ", ".join(f"'{point.name}' (id {point.id})" for point in phase_points)
    if len({point.id for point in phase_points}) != 3:
        raise SiteProfileConfigError(
            f"{quantity} imbalance needs three different points, got {point_names}"
        )
    if len({point.device_id for point in phase_points}) != 1:
        raise SiteProfileConfigError(
            f"{quantity} imbalance points must be on one device: {point_names}"
        )
    if len({point.unit for point in phase_points}) != 1:
        raise SiteProfileConfigError(
            f"{quantity} imbalance points must share one unit: {point_names}"
        )
    if min_mean <= 0:
        raise SiteProfileConfigError(f"{quantity} imbalance min_mean must be > 0, got {min_mean}")


def spf_common_phase_imbalance_timeseries(
    quantity: PhaseQuantity,
    phase_points: tuple[DevicePointResponse, DevicePointResponse, DevicePointResponse],
    series_by_point: dict[int, PointTimeseries],
    min_mean: float,
) -> PhaseImbalanceTimeseries:
    """
    The imbalance of the three phases at every shared timestamp, from series already read.

    series_by_point: spf_common_get_point_timeseries' result for phase_points.
    """
    phase_a_point, phase_b_point, phase_c_point = phase_points
    return PhaseImbalanceTimeseries(
        quantity=quantity,
        device_id=phase_a_point.device_id,
        unit=phase_a_point.unit,
        min_mean=min_mean,
        phase_point_ids=(phase_a_point.id, phase_b_point.id, phase_c_point.id),
        samples=_spf_common_phase_imbalance_samples(
            series_by_point[phase_a_point.id].timeseries,
            series_by_point[phase_b_point.id].timeseries,
            series_by_point[phase_c_point.id].timeseries,
            min_mean,
        ),
    )


def _spf_common_first_and_last_value(samples: list[TimeseriesPoint]) -> tuple[float, float] | None:
    """Oldest and newest non-null values; None with fewer than two."""
    readings = sorted((sample.time, sample.value) for sample in samples if sample.value is not None)
    if len(readings) < 2:
        return None
    return readings[0][1], readings[-1][1]


def _spf_common_stored_energy_change_kwh(
    soc_start_pct: float, soc_end_pct: float, usable_energy_kwh: float
) -> float:
    """Delta S = (SoC end - SoC start) / 100 * usable energy. > 0: ended fuller; < 0: emptier."""
    return (soc_end_pct - soc_start_pct) / 100 * usable_energy_kwh


def _spf_common_round_trip_efficiency(
    charged_kwh: float, discharged_kwh: float, stored_energy_change_kwh: float
) -> float:
    """
    Round trip efficiency (0-1) from energy in, energy out and the change in stored energy.

    Energy balance:  eta_ch * E_ch - E_dis / eta_dis = Delta S
    With symmetric losses (eta_ch = eta_dis = x) that is  E_ch*x^2 - Delta S*x - E_dis = 0, so

        x = (Delta S + sqrt(Delta S^2 + 4 * E_ch * E_dis)) / (2 * E_ch)        eta_RT = x^2

    With Delta S = 0 it is exactly E_dis / E_ch. Unlike (E_dis + Delta S) / E_ch, stored energy
    gets no credit it has not yet lost on its way out.
    """
    if charged_kwh <= 0:
        raise ValueError(f"charged_kwh must be > 0, got {charged_kwh}")
    one_way_efficiency = (
        stored_energy_change_kwh
        + math.sqrt(stored_energy_change_kwh**2 + 4 * charged_kwh * discharged_kwh)
    ) / (2 * charged_kwh)
    return one_way_efficiency**2


def spf_common_round_trip_efficiency_result(
    *,
    boundary: RoundTripBoundary,
    energy_source: Literal["power", "counters"],
    charged_kwh: float,
    discharged_kwh: float,
    aux_kwh: float | None,
    soc_samples: list[TimeseriesPoint],
    settings: RoundTripEfficiencySettings,
) -> RoundTripEfficiencyResult:
    """
    The round trip efficiency result, or the reason it can't be trusted (status).

    aux_kwh (system boundary only) is counted as energy in: E_ch + E_aux. The checks run in
    order: SoC data present, enough charged energy, SoC change small enough.
    """
    result = RoundTripEfficiencyResult(
        boundary=boundary,
        energy_source=energy_source,
        status="missing_soc_data",
        round_trip_efficiency_pct=None,
        method=None,
        charged_kwh=charged_kwh,
        discharged_kwh=discharged_kwh,
        aux_kwh=aux_kwh,
        soc_start_pct=None,
        soc_end_pct=None,
        stored_energy_change_kwh=None,
    )
    soc = _spf_common_first_and_last_value(soc_samples)
    if soc is None:
        return result

    soc_start_pct, soc_end_pct = soc
    stored_energy_change_kwh = _spf_common_stored_energy_change_kwh(
        soc_start_pct, soc_end_pct, settings.usable_energy_kwh
    )
    result.soc_start_pct = soc_start_pct
    result.soc_end_pct = soc_end_pct
    result.stored_energy_change_kwh = stored_energy_change_kwh

    energy_in_kwh = charged_kwh + (aux_kwh or 0.0)
    if energy_in_kwh < settings.min_charged_kwh:
        result.status = "insufficient_throughput"
    elif abs(soc_end_pct - soc_start_pct) > settings.max_soc_change_pct:
        result.status = "soc_change_too_large"
    else:
        round_trip_efficiency_pct = 100 * _spf_common_round_trip_efficiency(
            energy_in_kwh, discharged_kwh, stored_energy_change_kwh
        )
        result.round_trip_efficiency_pct = round_trip_efficiency_pct
        result.method = "closed_cycle" if stored_energy_change_kwh == 0 else "soc_corrected"
        result.status = "above_100_percent" if round_trip_efficiency_pct > 100 else "ok"
    return result
