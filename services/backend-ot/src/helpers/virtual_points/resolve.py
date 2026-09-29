"""Compute a virtual point's values from its inputs' stored readings (compute on read).

Pure: no I/O. The read helpers (`helpers.reads.device_points_readings`) load the inputs' stored
readings and call these; nothing computed here is written anywhere.

Inputs usually come from different devices, polled a moment apart, so their timestamps don't
match. Each input carries its last value forward, for at most `max_gap`, and output samples are
produced at the inputs' timestamps. Timestamps within `ALIGN_TOLERANCE` of each other (one poll
cycle across devices) collapse into one output sample.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta

from config import settings
from helpers.virtual_points.definition import referenced_point_ids
from helpers.virtual_points.evaluate import evaluate_virtual_point
from schemas.api_models.virtual_points import VirtualDefinition
from schemas.internal_models import TimestampedValue

ALIGN_TOLERANCE = timedelta(seconds=1)
# An input value is used for up to this many poll intervals after it was read, so one missed
# poll doesn't blank the virtual point.
MAX_GAP_POLL_INTERVALS = 3


def input_max_gap() -> timedelta:
    return timedelta(seconds=MAX_GAP_POLL_INTERVALS * settings.poll_interval_seconds)


def _event_times(series: Mapping[int, list[TimestampedValue]]) -> list[datetime]:
    """Union of the input timestamps, each cluster within ALIGN_TOLERANCE of its first time
    collapsed onto its last time."""
    events: list[datetime] = []
    cluster_start: datetime | None = None
    for time in sorted({sample.time for samples in series.values() for sample in samples}):
        if cluster_start is not None and time - cluster_start < ALIGN_TOLERANCE:
            events[-1] = time
        else:
            cluster_start = time
            events.append(time)
    return events


def evaluate_series(
    definition: VirtualDefinition, inputs: Mapping[int, list[TimestampedValue]], max_gap: timedelta
) -> list[TimestampedValue]:
    """The virtual point's samples, oldest first. A time where any input has no value within
    `max_gap` (or where the definition yields None, e.g. a ratio by 0) produces no sample."""
    series = {
        point_id: sorted(inputs.get(point_id, []), key=lambda sample: sample.time)
        for point_id in referenced_point_ids(definition)
    }
    if not series or any(not samples for samples in series.values()):
        return []

    positions = dict.fromkeys(series, -1)
    output: list[TimestampedValue] = []
    for time in _event_times(series):
        values: dict[int, float | None] = {}
        for point_id, samples in series.items():
            position = positions[point_id]
            while position + 1 < len(samples) and samples[position + 1].time <= time:
                position += 1
            positions[point_id] = position
            current = samples[position] if position >= 0 else None
            values[point_id] = current.value if current is not None and time - current.time <= max_gap else None
        value = evaluate_virtual_point(definition, values)
        if value is not None:
            output.append(TimestampedValue(time=time, value=value))
    return output


def evaluate_latest(
    definition: VirtualDefinition, latest: Mapping[int, TimestampedValue | None], max_gap: timedelta
) -> TimestampedValue | None:
    """The virtual point's current value, at its newest input's time. None when an input has no
    reading or is more than `max_gap` older than the newest input."""
    samples: dict[int, TimestampedValue] = {}
    for point_id in referenced_point_ids(definition):
        sample = latest.get(point_id)
        if sample is None:
            return None
        samples[point_id] = sample
    if not samples:
        return None
    newest = max(sample.time for sample in samples.values())
    if any(newest - sample.time > max_gap for sample in samples.values()):
        return None
    value = evaluate_virtual_point(definition, {point_id: sample.value for point_id, sample in samples.items()})
    return TimestampedValue(time=newest, value=value) if value is not None else None
