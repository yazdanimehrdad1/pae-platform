"""Line up time series from several points at their own sample times (no resampling).

Pure: no I/O. Points on different devices are polled a moment apart, so their timestamps don't
match. Each series carries its last value forward, for at most `max_gap`, and aligned samples are
produced at the series' own timestamps. Timestamps within `ALIGN_TOLERANCE` of each other (one
poll cycle across devices) collapse into one aligned sample, at the cluster's last time.

Used by virtual points (helpers.virtual_points.resolve) and by site functions that combine points
from several devices (site_profiles.common.shared_helper_functions.spf_common_combine_series).
"""

from collections.abc import Mapping
from datetime import datetime, timedelta

from config import settings
from schemas.internal_models import AlignedValues, TimestampedValue

ALIGN_TOLERANCE = timedelta(seconds=1)
# A value is used for up to this many poll intervals after it was read, so one missed poll
# doesn't blank a combined series.
MAX_GAP_POLL_INTERVALS = 3


def default_max_gap() -> timedelta:
    return timedelta(seconds=MAX_GAP_POLL_INTERVALS * settings.poll_interval_seconds)


def aligned_times(series: Mapping[int, list[TimestampedValue]]) -> list[datetime]:
    """Union of the series' timestamps, each cluster within ALIGN_TOLERANCE of its first time
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


def align_series(
    series: Mapping[int, list[TimestampedValue]], max_gap: timedelta
) -> list[AlignedValues]:
    """
    Every key's value at each aligned time, oldest first: its latest sample at or before that
    time, or None when it has none within `max_gap`. Each key in `series` appears in every
    AlignedValues.values. Samples may be in any order.
    """
    ordered = {key: sorted(samples, key=lambda sample: sample.time) for key, samples in series.items()}
    positions = dict.fromkeys(ordered, -1)
    aligned: list[AlignedValues] = []
    for time in aligned_times(ordered):
        values: dict[int, float | None] = {}
        for key, samples in ordered.items():
            position = positions[key]
            while position + 1 < len(samples) and samples[position + 1].time <= time:
                position += 1
            positions[key] = position
            current = samples[position] if position >= 0 else None
            values[key] = current.value if current is not None and time - current.time <= max_gap else None
        aligned.append(AlignedValues(time=time, values=values))
    return aligned
