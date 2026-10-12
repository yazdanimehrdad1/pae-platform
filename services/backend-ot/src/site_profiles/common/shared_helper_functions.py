"""
Helper functions every device type shares: the one historian read, unit conversion and
power/energy integration.

Naming: spf_common_<name> is called from outside this file (a device-type package under
common/ or a site package); _spf_common_<name> is only called inside it. Everything except
spf_common_get_point_timeseries (the historian read) is pure: no DB, no network, no clock.
"""

from bisect import bisect_left, bisect_right
from datetime import UTC, datetime, timedelta

from helpers.reads.device_points_readings import get_timeseries_by_point_ids
from schemas.api_models import (
    DevicePointResponse,
    PointTimeseries,
    TimeseriesPoint,
)
from schemas.site_profiles import (
    SeriesInterval,
    SiteContext,
    TimeWindow,
)

POWER_UNIT_TO_KW: dict[str, float] = {"W": 0.001, "kW": 1.0, "MW": 1000.0}
ENERGY_UNIT_TO_KWH: dict[str, float] = {"Wh": 0.001, "kWh": 1.0, "MWh": 1000.0}

SERIES_INTERVAL_LENGTHS: dict[SeriesInterval, timedelta] = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "1d": timedelta(days=1),
}
# The interval picked for a window up to each length; anything longer gets "1d".
_AUTO_INTERVALS: tuple[tuple[timedelta, SeriesInterval], ...] = (
    (timedelta(hours=1), "5m"),
    (timedelta(hours=6), "15m"),
    (timedelta(hours=12), "30m"),
    (timedelta(days=3), "1h"),
    (timedelta(weeks=1), "6h"),
)
MAX_SERIES_INTERVALS = 2000


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


def spf_common_pick_interval(window: TimeWindow) -> SeriesInterval:
    """The interval for a series over `window` when the caller didn't ask for one."""
    length = window.end_time - window.start_time
    for longest, interval in _AUTO_INTERVALS:
        if length <= longest:
            return interval
    return "1d"


def spf_common_interval_starts(window: TimeWindow, interval: SeriesInterval) -> list[datetime]:
    """
    The start (aware UTC) of every interval that overlaps `window`, oldest first. The first may
    begin before the window: starts are aligned, sub-daily ones to multiples of their length in
    UTC, daily ones to midnight in the window's display zone (UTC without one), so that a day
    is a calendar day even across a DST change. More than MAX_SERIES_INTERVALS is a ValueError.
    """
    length = SERIES_INTERVAL_LENGTHS[interval]
    if (window.end_time - window.start_time) / length > MAX_SERIES_INTERVALS:
        raise ValueError(
            f"interval {interval} gives more than {MAX_SERIES_INTERVALS} intervals over this window; "
            "use a longer interval or a shorter window"
        )
    starts: list[datetime] = []
    if interval == "1d":
        zone = window.display_tz or UTC
        local = window.start_time.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
        while local.astimezone(UTC) < window.end_time:
            starts.append(local.astimezone(UTC))
            local += length  # a wall-clock day: next midnight, 23 or 25 h later across DST
        return starts
    seconds = int(length.total_seconds())
    epoch = int(window.start_time.timestamp())
    start = datetime.fromtimestamp(epoch - epoch % seconds, UTC)
    while start < window.end_time:
        starts.append(start)
        start += length
    return starts


def spf_common_energy_kwh_per_interval(
    samples: list[TimeseriesPoint], unit: str | None, interval_starts: list[datetime]
) -> list[float]:
    """
    Energy in kWh in each interval, from power samples: interval i runs from interval_starts[i]
    to interval_starts[i + 1] (the last one to the last sample). The same trapezoids as
    spf_common_integrate_power_to_energy_kwh, so the intervals add up to its total; a trapezoid
    that spans an interval start is split there at the linearly interpolated power. Power before
    the first start is not counted. Same PLACEHOLDER gap rule.
    """
    factor = spf_common_power_unit_to_kw_factor(unit)
    readings: list[tuple[datetime, float]] = sorted(  # (time, kW), oldest first
        (sample.time, sample.value * factor) for sample in samples if sample.value is not None
    )
    totals = [0.0] * len(interval_starts)
    for (previous_time, previous_kw), (current_time, current_kw) in zip(
        readings, readings[1:], strict=False
    ):
        span = current_time - previous_time
        if span <= timedelta(0):
            continue
        inside = interval_starts[
            bisect_right(interval_starts, previous_time) : bisect_left(interval_starts, current_time)
        ]
        cuts = [previous_time, *inside, current_time]
        for left, right in zip(cuts, cuts[1:], strict=False):
            index = bisect_right(interval_starts, left) - 1
            if index < 0:
                continue
            left_kw = previous_kw + (current_kw - previous_kw) * ((left - previous_time) / span)
            right_kw = previous_kw + (current_kw - previous_kw) * ((right - previous_time) / span)
            totals[index] += (left_kw + right_kw) / 2 * (right - left).total_seconds() / 3600
    return totals


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
