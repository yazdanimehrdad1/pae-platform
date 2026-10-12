"""Plot values and gap markers for one series, in Python (see README.md, "Long windows").

Pure: no I/O. Used for series computed in Python (virtual points, site functions) and for raw
stored readings; stored readings over a long window are reduced in Postgres instead
(plot_values_sql.py), with the same rule.

Plot values are a subset of the real samples, never new values: the window is cut into
max_points // 4 equal slices, and each slice keeps its first, last, lowest and highest sample
(an enum or bit point keeps its first, last and every change of value instead). A gap longer
than max_gap (an outage) keeps both of its edge samples and gets a gap marker: a sample with a
null value at the gap's midpoint, so a chart breaks the line there instead of bridging it.
"""

from bisect import bisect_right
from datetime import datetime, timedelta
from typing import TypeVar, get_args

from pydantic import BaseModel

from helpers.sampling.policy import use_plot_values
from schemas.api_models import PointTimeseries, TimeseriesPoint
from schemas.api_models.types import ExtendedDataType
from schemas.internal_models import PointReading

# Enum, bitfield and status word points (and bool): their values are states, not magnitudes.
DISCRETE_DATA_TYPES: frozenset[str] = frozenset(get_args(ExtendedDataType)) | {"bool"}

SAMPLES_PER_SLICE = 4  # first, last, lowest, highest

ResponseT = TypeVar("ResponseT", bound=BaseModel)


def is_discrete(data_type: str) -> bool:
    return data_type in DISCRETE_DATA_TYPES


def gap_marker_time(before: datetime, after: datetime) -> datetime:
    """Where a gap marker goes: halfway between the samples on each side of the gap."""
    return before + (after - before) / 2


def sample_series(
    samples: list[TimeseriesPoint],
    start: datetime,
    end: datetime,
    max_points: int | None,
    max_gap: timedelta,
    discrete: bool,
) -> list[TimeseriesPoint]:
    """
    What a chart gets for one series, oldest first. Without max_points: the samples unchanged.
    With it: plot values when use_plot_values says so, otherwise every sample; either way with
    gap markers. Samples may come in any order.
    """
    if max_points is None:
        return samples
    ordered = sorted(samples, key=lambda sample: sample.time)
    if not use_plot_values(start, end, max_points):
        return _with_gap_markers(ordered, list(range(len(ordered))), max_gap)
    return _with_gap_markers(ordered, _plot_value_indexes(ordered, start, end, max_points, max_gap, discrete), max_gap)


def _plot_value_indexes(
    ordered: list[TimeseriesPoint],
    start: datetime,
    end: datetime,
    max_points: int,
    max_gap: timedelta,
    discrete: bool,
) -> list[int]:
    """Indexes (into the time-ordered samples) of the samples kept as plot values."""
    slices = max(1, max_points // SAMPLES_PER_SLICE)
    slice_length = (end - start) / slices
    edges = [start + slice_length * index for index in range(1, slices)]
    kept: set[int] = set()
    by_slice: dict[int, list[int]] = {}
    for index, sample in enumerate(ordered):
        if index > 0 and sample.time - ordered[index - 1].time > max_gap:
            kept.update((index - 1, index))  # both edges of a gap
        if sample.value is None:
            continue
        by_slice.setdefault(bisect_right(edges, sample.time), []).append(index)
    for indexes in by_slice.values():
        kept.update((indexes[0], indexes[-1]))
        if discrete:
            continue
        kept.add(min(indexes, key=lambda index: ordered[index].value or 0.0))
        kept.add(max(indexes, key=lambda index: ordered[index].value or 0.0))
    if discrete:
        values = [(index, sample.value) for index, sample in enumerate(ordered) if sample.value is not None]
        kept.update(index for (_, previous), (index, value) in zip(values, values[1:], strict=False) if value != previous)
    return sorted(kept)


def _with_gap_markers(ordered: list[TimeseriesPoint], indexes: list[int], max_gap: timedelta) -> list[TimeseriesPoint]:
    """The samples at `indexes`, with a gap marker before each one that ends a gap in the full
    series (gaps are judged on all samples, not on the kept ones)."""
    output: list[TimeseriesPoint] = []
    for index in indexes:
        sample = ordered[index]
        if index > 0 and sample.time - ordered[index - 1].time > max_gap:
            output.append(TimeseriesPoint(time=gap_marker_time(ordered[index - 1].time, sample.time), value=None))
        output.append(sample)
    return output


def sample_readings(
    readings: list[PointReading],
    start: datetime,
    end: datetime,
    max_points: int | None,
    max_gap: timedelta,
) -> list[PointReading]:
    """sample_series for readings of several points (any order), returned newest first per point
    like the readings queries; a gap marker is a reading of its point with derived_value None."""
    if max_points is None:
        return readings
    by_point: dict[int, list[PointReading]] = {}
    for reading in readings:
        if reading.timestamp is not None:
            by_point.setdefault(reading.device_point_id, []).append(reading)
    output: list[PointReading] = []
    for point_id in sorted(by_point):
        point_readings = by_point[point_id]
        template = point_readings[0]
        samples = [TimeseriesPoint(time=reading.timestamp, value=reading.derived_value) for reading in point_readings]
        sampled = sample_series(samples, start, end, max_points, max_gap, is_discrete(template.data_type))
        output += [
            template.model_copy(update={"timestamp": sample.time, "derived_value": sample.value})
            for sample in reversed(sampled)
        ]
    return output


def sample_point_timeseries(
    series: PointTimeseries, start: datetime, end: datetime, max_points: int | None, max_gap: timedelta
) -> PointTimeseries:
    """sample_series for a PointTimeseries (as a site function returns it), count updated."""
    sampled = sample_series(series.timeseries, start, end, max_points, max_gap, is_discrete(series.data_type))
    return series.model_copy(update={"timeseries": sampled, "count": len(sampled)})


def sample_series_response(
    response: ResponseT, start: datetime, end: datetime, max_points: int | None, max_gap: timedelta
) -> ResponseT:
    """A series endpoint's response with its `series` (one PointTimeseries or a list) sampled
    for a chart; the rest of the response is untouched. The profile registry guarantees the field."""
    series = response.series
    if isinstance(series, list):
        sampled: PointTimeseries | list[PointTimeseries] = [
            sample_point_timeseries(entry, start, end, max_points, max_gap) for entry in series
        ]
    else:
        sampled = sample_point_timeseries(series, start, end, max_points, max_gap)
    return response.model_copy(update={"series": sampled})
