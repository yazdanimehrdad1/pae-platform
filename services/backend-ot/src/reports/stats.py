"""Point statistics computed in Python, for points whose readings aren't stored (virtual points).
Stored points get the same statistics from Postgres (backend_ot_source.py); both bucket by the
site's local hour or day."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from schemas.reports.definition import PointStat
from schemas.reports.internal import PointStatValues

ALL_STATS: tuple[PointStat, ...] = ("min", "max", "avg", "first", "last", "count")


def bucket_start(time: datetime, bucket: str, site_timezone: ZoneInfo) -> datetime | None:
    """The start (UTC) of the local hour or day `time` falls in; None for bucket 'none'."""
    if bucket == "none":
        return None
    local = time.astimezone(site_timezone)
    if bucket == "hour":
        floored = local.replace(minute=0, second=0, microsecond=0)
    else:
        floored = datetime(local.year, local.month, local.day, tzinfo=site_timezone)
    return floored.astimezone(UTC)


def compute_point_stats(
    point_id: int, samples: list[tuple[datetime, float]], bucket: str, site_timezone: ZoneInfo
) -> list[PointStatValues]:
    """Statistics of (time, value) samples, in any order: one entry per bucket that has samples,
    oldest bucket first (a single entry for bucket 'none', none at all without samples)."""
    by_bucket: dict[datetime | None, list[tuple[datetime, float]]] = {}
    for time, value in sorted(samples, key=lambda sample: sample[0]):
        by_bucket.setdefault(bucket_start(time, bucket, site_timezone), []).append((time, value))
    return [
        PointStatValues(point_id=point_id, bucket_start=start, values=_stats([value for _, value in bucket_samples]))
        for start, bucket_samples in by_bucket.items()
    ]


def _stats(values: list[float]) -> dict[PointStat, float | None]:
    return {
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "first": values[0],
        "last": values[-1],
        "count": float(len(values)),
    }
