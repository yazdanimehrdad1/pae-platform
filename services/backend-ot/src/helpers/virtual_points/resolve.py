"""Compute a virtual point's values from its inputs' stored readings (compute on read).

Pure: no I/O. The read helpers (`helpers.reads.device_points_readings`) load the inputs' stored
readings and call these; nothing computed here is written anywhere.

Inputs usually come from different devices, polled a moment apart, so their timestamps don't
match. They are lined up by helpers.common.series_alignment: each input carries its last value
forward, for at most `max_gap`, output samples are produced at the inputs' timestamps, and one
poll cycle across devices (ALIGN_TOLERANCE) collapses into one output sample.
"""

from collections.abc import Mapping
from datetime import timedelta

from helpers.common.series_alignment import align_series, default_max_gap
from helpers.virtual_points.definition import referenced_point_ids
from helpers.virtual_points.evaluate import evaluate_virtual_point
from schemas.api_models.virtual_points import VirtualDefinition
from schemas.internal_models import TimestampedValue


def input_max_gap() -> timedelta:
    """How long an input's value is used after it was read (MAX_GAP_POLL_INTERVALS polls)."""
    return default_max_gap()


def evaluate_series(
    definition: VirtualDefinition, inputs: Mapping[int, list[TimestampedValue]], max_gap: timedelta
) -> list[TimestampedValue]:
    """The virtual point's samples, oldest first. A time where any input has no value within
    `max_gap` (or where the definition yields None, e.g. a ratio by 0) produces no sample."""
    series = {point_id: inputs.get(point_id, []) for point_id in referenced_point_ids(definition)}
    if not series or any(not samples for samples in series.values()):
        return []

    output: list[TimestampedValue] = []
    for aligned in align_series(series, max_gap):
        value = evaluate_virtual_point(definition, aligned.values)
        if value is not None:
            output.append(TimestampedValue(time=aligned.time, value=value))
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
