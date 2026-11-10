"""Running an approved site function the way the AI gets it: one path for the
`run_site_function` tool and the admin's test-run, so the admin sees exactly what Claude sees
(and, for checking, backend-ot's untouched result next to it).

backend-ot computes the function; the gated connector (site_profile/gate.py) refuses functions,
devices and parameters that are not approved. A series result is fetched with every reading
(no backend-ot sampling) over at most `series_max_hours`, and each series is reduced here:
- "15min" (the default): a plain time series, [{time, value}], holding the first reading of each
  15-minute interval (UTC) at its own timestamp: every row is a real backend-ot reading;
- "raw": every reading, compact: `start`, `offsets_s` (whole seconds after it) and `values`.
Both add the gaps (no reading for longer than 3 typical poll steps, or at the window's edges) and
the share of the window that has data, so the AI never mistakes missing data for a value.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Literal

from pydantic import JsonValue

from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.schemas.site_data import SiteFunctionRun
from intelli_gateway.utils.exceptions import InvalidRequestError, NotFoundError

SeriesResolution = Literal["15min", "raw"]

# A pause longer than this many typical poll steps is a gap (backend-ot's own rule).
GAP_STEPS = 3
# Raw values are rounded to this many decimals (fewer tokens; far finer than any meter).
DECIMALS = 3


@dataclass(frozen=True)
class FunctionLimits:
    max_days: int  # any function's window
    series_max_hours: int  # a series function's window
    interval_minutes: int  # the "15min" resolution's interval


@dataclass(frozen=True)
class FunctionRunResult:
    for_ai: dict[str, JsonValue]  # what the AI gets
    backend_ot: dict[str, JsonValue]  # backend-ot's untouched result (admin checks only)


@dataclass(frozen=True)
class Reading:
    time: datetime
    value: float
    raw_time: str  # the timestamp exactly as backend-ot sent it


async def run_function(
    site_data: SiteDataConnector,
    site_id: int,
    run: SiteFunctionRun,
    resolution: SeriesResolution,
    limits: FunctionLimits,
) -> FunctionRunResult:
    if run.end <= run.start:
        raise InvalidRequestError("the window's end must be after its start")
    functions = await site_data.list_site_functions(site_id)
    function = next((f for f in functions if f.name == run.name), None)
    if function is None:
        raise NotFoundError(f"no approved site function named {run.name!r}")
    window = run.end - run.start
    if function.output == "series":
        if window > timedelta(hours=limits.series_max_hours):
            raise InvalidRequestError(
                f"series data is limited to {limits.series_max_hours} hours; for a longer period "
                "use a site function that computes the answer (a scalar result)"
            )
    elif window > timedelta(days=limits.max_days):
        raise InvalidRequestError(f"the window is longer than {limits.max_days} days; shorten it")
    # No max_points: backend-ot returns every reading in the window.
    result = await site_data.run_site_function(site_id, run)
    if function.output != "series":
        return FunctionRunResult(for_ai=result, backend_ot=result)
    interval = timedelta(minutes=limits.interval_minutes)
    reduced = reduce_result(result, run.start, run.end, resolution, interval)
    for_ai: dict[str, JsonValue] = reduced if isinstance(reduced, dict) else {"result": reduced}
    return FunctionRunResult(for_ai=for_ai, backend_ot=result)


def reduce_result(
    content: JsonValue,
    start: datetime,
    end: datetime,
    resolution: SeriesResolution,
    interval: timedelta,
) -> JsonValue:
    """The result with every series (an object with a `timeseries` list) reduced."""
    if isinstance(content, list):
        return [reduce_result(item, start, end, resolution, interval) for item in content]
    if not isinstance(content, dict):
        return content
    samples = content.get("timeseries")
    if isinstance(samples, list):
        readings = parse_readings(samples, start, end)
        series: dict[str, JsonValue] = {
            key: value for key, value in content.items() if key != "timeseries"
        }
        if resolution == "raw":
            series["resolution"] = "every reading"
            series["timeseries"] = compact_raw(readings, start)
        else:
            series["resolution"] = f"first reading every {round(interval.total_seconds() / 60)} min"
            series["timeseries"] = first_per_interval(readings, interval)
        return {**series, **gap_summary(readings, start, end)}
    return {
        key: reduce_result(value, start, end, resolution, interval)
        for key, value in content.items()
    }


def parse_readings(samples: list[JsonValue], start: datetime, end: datetime) -> list[Reading]:
    """backend-ot's [{time, value}, ...] inside the window, oldest first. Samples without a
    number (backend-ot's gap markers, bad data) are skipped."""
    readings: list[Reading] = []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        raw_time, value = sample.get("time"), sample.get("value")
        if not isinstance(raw_time, str) or isinstance(value, bool):
            continue
        if not isinstance(value, int | float):
            continue
        try:
            time = datetime.fromisoformat(raw_time)
        except ValueError:
            continue
        if time.tzinfo is not None and start <= time <= end:
            readings.append(Reading(time, float(value), raw_time))
    readings.sort(key=lambda reading: reading.time)
    return readings


def first_per_interval(readings: list[Reading], interval: timedelta) -> list[JsonValue]:
    """The first reading of each interval (whole multiples of `interval` since the epoch, UTC),
    exactly as backend-ot sent it. An interval without a reading has no row (see the gaps)."""
    picked: list[JsonValue] = []
    last_interval: datetime | None = None
    for reading in readings:
        current = floor_time(reading.time, interval)
        if current != last_interval:
            picked.append({"time": reading.raw_time, "value": reading.value})
            last_interval = current
    return picked


def compact_raw(readings: list[Reading], start: datetime) -> dict[str, JsonValue]:
    """Every reading: whole seconds after the window start, and the values."""
    return {
        "start": start.isoformat(),
        "offsets_s": [round((reading.time - start).total_seconds()) for reading in readings],
        "values": [round(reading.value, DECIMALS) for reading in readings],
    }


def find_gaps(
    readings: list[Reading], start: datetime, end: datetime
) -> list[tuple[datetime, datetime]]:
    """Stretches with no reading: longer than GAP_STEPS typical steps between readings or at
    the window's edges. No reading at all = the whole window."""
    if not readings:
        return [(start, end)]
    steps = [
        (b.time - a.time).total_seconds() for a, b in zip(readings, readings[1:], strict=False)
    ]
    positive = [step for step in steps if step > 0]
    if not positive:
        return []
    limit = timedelta(seconds=GAP_STEPS * median(positive))
    edges = [start, *(reading.time for reading in readings), end]
    return [(a, b) for a, b in zip(edges, edges[1:], strict=False) if b - a > limit]


def gap_summary(readings: list[Reading], start: datetime, end: datetime) -> dict[str, JsonValue]:
    gaps = find_gaps(readings, start, end)
    missing = sum((b - a for a, b in gaps), timedelta())
    return {
        "gaps": [
            {
                "start": a.isoformat(),
                "end": b.isoformat(),
                "minutes": round((b - a).total_seconds() / 60, 1),
            }
            for a, b in gaps
        ],
        "coverage_percent": round(100 * (1 - missing / (end - start)), 1),
    }


def floor_time(time: datetime, step: timedelta) -> datetime:
    """`time` rounded down to a whole multiple of `step` since the epoch (in UTC)."""
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return epoch + ((time - epoch) // step) * step
