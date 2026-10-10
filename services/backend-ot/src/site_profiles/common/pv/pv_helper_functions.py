"""
PV helper functions behind common/pv/pv_functions.py. Pure: no DB, no network, no clock.

Naming: spf_common_<name> is called from outside this file (pv_functions.py or a site
package); _spf_common_<name> is only called inside it. Helpers every device type uses live in
common/shared_helper_functions.py.
"""

from datetime import datetime

from schemas.api_models import TimeseriesPoint
from schemas.site_profiles import PvPowerSignConvention, PvPowerStats
from site_profiles.common.shared_helper_functions import (
    spf_common_power_unit_to_kw_factor,
    spf_common_split_power_by_sign_kwh,
)


def _spf_common_pv_producing_energy_and_hours(
    readings_kw: list[tuple[datetime, float]], producing_threshold_kw: float
) -> tuple[float, float]:
    """
    (energy_kwh, hours) over the intervals whose two ends are both at or above the threshold.

    readings_kw: (time, kW) oldest first, + production. Dawn and dusk intervals, where one end
    is below the threshold, are left out rather than guessing where production began.
    """
    energy_kwh = 0.0
    hours = 0.0
    for (previous_time, previous_kw), (current_time, current_kw) in zip(
        readings_kw, readings_kw[1:], strict=False
    ):
        if previous_kw >= producing_threshold_kw and current_kw >= producing_threshold_kw:
            interval_hours = (current_time - previous_time).total_seconds() / 3600
            energy_kwh += (previous_kw + current_kw) / 2 * interval_hours
            hours += interval_hours
    return energy_kwh, hours


def spf_common_pv_power_stats_from_samples(
    samples: list[TimeseriesPoint],
    unit: str | None,
    producing_threshold_kw: float,
    sign_convention: PvPowerSignConvention = "positive_is_production",
) -> PvPowerStats:
    """
    Peak, average and minimum power, and energy produced and consumed, of one PV power point.

    producing_threshold_kw: power at or above which the plant counts as producing (e.g. 1 % of
        rated power); it gives the producing-hours average and minimum, which leave the night out.
    sign_convention: "positive_is_consumption" for a meter that reports production as negative;
        its values are flipped first.

    Samples may be in any order; null values are skipped. average_kw is time-weighted (net energy
    / covered duration); with one sample, or all at one instant, it is the plain mean. Same
    PLACEHOLDER gap rule as spf_common_integrate_power_to_energy_kwh.
    """
    if producing_threshold_kw <= 0:
        raise ValueError(f"producing_threshold_kw must be > 0, got {producing_threshold_kw}")
    factor = spf_common_power_unit_to_kw_factor(unit)
    sign = 1.0 if sign_convention == "positive_is_production" else -1.0
    readings_kw: list[tuple[datetime, float]] = sorted(  # (time, kW), oldest first, + production
        (sample.time, sample.value * sign * factor)
        for sample in samples
        if sample.value is not None
    )
    production_positive_kw = [TimeseriesPoint(time=time, value=kw) for time, kw in readings_kw]
    energy_produced_kwh, energy_consumed_kwh = spf_common_split_power_by_sign_kwh(
        production_positive_kw, "kW"
    )
    producing_energy_kwh, producing_hours = _spf_common_pv_producing_energy_and_hours(
        readings_kw, producing_threshold_kw
    )

    values_kw = [kw for _, kw in readings_kw]
    producing_values_kw = [kw for kw in values_kw if kw >= producing_threshold_kw]
    average_kw: float | None = None
    if values_kw:
        covered_hours = (readings_kw[-1][0] - readings_kw[0][0]).total_seconds() / 3600
        average_kw = (
            (energy_produced_kwh - energy_consumed_kwh) / covered_hours
            if covered_hours > 0
            else sum(values_kw) / len(values_kw)
        )
    return PvPowerStats(
        sample_count=len(values_kw),
        energy_produced_kwh=energy_produced_kwh,
        energy_consumed_kwh=energy_consumed_kwh,
        peak_kw=max(values_kw) if values_kw else None,
        average_kw=average_kw,
        min_kw=min(values_kw) if values_kw else None,
        producing_threshold_kw=producing_threshold_kw,
        producing_hours=producing_hours,
        average_producing_kw=producing_energy_kwh / producing_hours
        if producing_hours > 0
        else None,
        min_producing_kw=min(producing_values_kw) if producing_values_kw else None,
    )
