"""
Helper functions every device type shares: the one historian read, unit conversion and
power/energy integration.

Naming: spf_common_<name> is called from outside this file (a device-type package under
common/ or a site package); _spf_common_<name> is only called inside it. Everything except
spf_common_get_point_timeseries (the historian read) is pure: no DB, no network, no clock.
"""

from datetime import datetime

from helpers.reads.device_points_readings import get_timeseries_by_point_ids
from schemas.api_models import (
    DevicePointResponse,
    PointTimeseries,
    TimeseriesPoint,
)
from schemas.site_profiles import (
    SiteContext,
    TimeWindow,
)

POWER_UNIT_TO_KW: dict[str, float] = {"W": 0.001, "kW": 1.0, "MW": 1000.0}
ENERGY_UNIT_TO_KWH: dict[str, float] = {"Wh": 0.001, "kWh": 1.0, "MWh": 1000.0}


def spf_common_power_unit_to_kw_factor(unit: str | None) -> float:
    """Multiplier that converts a power point's unit to kW. Unknown units are an error."""
    if unit not in POWER_UNIT_TO_KW:
        raise ValueError(
            f"Unsupported power unit {unit!r}; expected one of {list(POWER_UNIT_TO_KW)}"
        )
    return POWER_UNIT_TO_KW[unit]


def spf_common_integrate_power_to_energy_kwh(
    samples: list[TimeseriesPoint], unit: str | None
) -> float:
    """
    Energy in kWh from power samples, by trapezoidal integration over time.

    Samples may be in any order; null values are skipped. Fewer than two samples give 0.
    PLACEHOLDER: a gap in polling is bridged by a straight line, which over-counts
    energy across outages. A real site will need a max-gap rule.
    """
    factor = spf_common_power_unit_to_kw_factor(unit)
    readings: list[tuple[datetime, float]] = sorted(
        (s.time, s.value) for s in samples if s.value is not None
    )
    total = 0.0
    for (previous_time, previous_value), (current_time, current_value) in zip(
        readings, readings[1:], strict=False
    ):
        hours = (current_time - previous_time).total_seconds() / 3600
        total += (previous_value + current_value) / 2 * hours * factor
    return total


def spf_common_mean_sample_value(samples: list[TimeseriesPoint]) -> float | None:
    """Mean of the non-null sample values; None when there are none."""
    values = [s.value for s in samples if s.value is not None]
    return sum(values) / len(values) if values else None


async def spf_common_get_point_timeseries(
    ctx: SiteContext, points: list[DevicePointResponse], window: TimeWindow
) -> dict[int, PointTimeseries]:
    """
    Every reading of `points` inside `window`, keyed by point id, OLDEST FIRST, with
    timestamps rendered in the window's display zone. A point with no readings in the
    window is still present, with an empty series. The one historian read behind every
    common function; site packages call it too.
    """
    series_by_point = {
        point.id: PointTimeseries(
            id=point.id,
            name=point.name,
            data_type=point.data_type,
            unit=point.unit,
            point_class=point.point_class,
            severity=point.severity,
        )
        for point in points
    }
    if not points:
        return series_by_point

    readings = await get_timeseries_by_point_ids(
        list(series_by_point),
        site_id=ctx.site.site_id,
        start_time=window.start_time,
        end_time=window.end_time,
        limit=None,
    )
    for reading in reversed(readings):  # readings come newest-first per point
        if reading.timestamp is None:  # only the latest query leaves it empty
            continue
        series = series_by_point[reading.device_point_id]
        series.timeseries.append(
            TimeseriesPoint(time=window.display(reading.timestamp), value=reading.derived_value)
        )
        series.count += 1
    return series_by_point


def _spf_common_energy_unit_to_kwh_factor(unit: str | None) -> float:
    """Multiplier that converts an energy point's unit to kWh. Unknown units are an error."""
    if unit not in ENERGY_UNIT_TO_KWH:
        raise ValueError(
            f"Unsupported energy unit {unit!r}; expected one of {list(ENERGY_UNIT_TO_KWH)}"
        )
    return ENERGY_UNIT_TO_KWH[unit]


def spf_common_split_power_by_sign_kwh(
    samples: list[TimeseriesPoint], unit: str | None
) -> tuple[float, float]:
    """
    (positive_kwh, negative_kwh) from net power samples: each sign integrated on its own.

        positive = integral of max(P, 0) dt        negative = integral of max(-P, 0) dt

    Both are >= 0; the caller says what each sign means (BESS discharge/charge, PV
    production/standby draw). Trapezoids between consecutive samples; an interval whose ends
    have opposite signs is split at its interpolated zero crossing, so the two never cancel
    inside it. Same PLACEHOLDER gap rule as spf_common_integrate_power_to_energy_kwh.
    """
    factor = spf_common_power_unit_to_kw_factor(unit)
    readings: list[tuple[datetime, float]] = sorted(  # (time, kW), oldest first
        (sample.time, sample.value * factor) for sample in samples if sample.value is not None
    )
    positive_kwh = 0.0
    negative_kwh = 0.0
    for (previous_time, previous_kw), (current_time, current_kw) in zip(
        readings, readings[1:], strict=False
    ):
        hours = (current_time - previous_time).total_seconds() / 3600
        if previous_kw * current_kw >= 0:
            # same sign (or one end at 0): one trapezoid, all one sign
            areas_kwh = [(previous_kw + current_kw) / 2 * hours]
        else:
            # the straight line crosses 0 at this fraction of the interval: two triangles
            crossing = previous_kw / (previous_kw - current_kw)
            areas_kwh = [
                previous_kw / 2 * crossing * hours,
                current_kw / 2 * (1 - crossing) * hours,
            ]
        for area_kwh in areas_kwh:
            if area_kwh > 0:
                positive_kwh += area_kwh
            else:
                negative_kwh -= area_kwh
    return positive_kwh, negative_kwh


def spf_common_counter_energy_kwh(
    samples: list[TimeseriesPoint], unit: str | None, counter_rollover: float | None
) -> float:
    """
    Energy a cumulative counter recorded in the window, in kWh: the sum of its increases.

    A drop is a wrap when the counter was in the top half of its range (it carries on from 0),
    otherwise a reset (that interval counts 0, the next one counts from the new value). With
    counter_rollover None every drop is a reset. counter_rollover is in the counter's unit.
    """
    factor = _spf_common_energy_unit_to_kwh_factor(unit)
    values = [
        value
        for _, value in sorted(
            (sample.time, sample.value) for sample in samples if sample.value is not None
        )
    ]
    increase = 0.0
    for previous, current in zip(values, values[1:], strict=False):
        if current >= previous:
            increase += current - previous
        elif counter_rollover is not None and previous > counter_rollover / 2:
            increase += current + counter_rollover - previous
    return increase * factor
