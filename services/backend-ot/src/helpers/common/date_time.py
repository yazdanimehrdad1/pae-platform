"""Datetime parsing and time-range helpers."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, available_timezones


def parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# Shorthand for zones people type by hand. Each alias resolves to an IANA *zone*, never
# to a fixed offset — so 'PDT' in January still yields -08:00, because the date decides
# the DST state. That makes the standard/daylight spelling irrelevant: PST and PDT are
# the same entry, and neither can be wrong for the date being queried.
#
# Deliberately US-only. Several abbreviations are ambiguous worldwide (CST is also China
# Standard Time, IST is India/Israel/Ireland, BST is British Summer/Bangladesh), so the
# list is limited to the fleet's own region and anything outside it must use a full IANA
# name.
_ZONE_ALIASES = {
    "PT": "America/Los_Angeles", "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles",
    "MT": "America/Denver", "MST": "America/Denver", "MDT": "America/Denver",
    "CT": "America/Chicago", "CST": "America/Chicago", "CDT": "America/Chicago",
    "ET": "America/New_York", "EST": "America/New_York", "EDT": "America/New_York",
    "AKT": "America/Anchorage", "AKST": "America/Anchorage", "AKDT": "America/Anchorage",
    "HT": "Pacific/Honolulu", "HST": "Pacific/Honolulu",
    "Z": "UTC", "GMT": "UTC",
}


@lru_cache(maxsize=1)
def _zones_by_lowercase() -> dict[str, str]:
    """
    Lowercased zone name -> canonical IANA name.

    ZoneInfo lookups are case-sensitive, so 'utc' and 'america/los_angeles' would fail
    while 'UTC' and 'America/Los_Angeles' succeed — a needless trap for a hand-typed
    query param. Lowercasing the tz database yields no collisions, so this mapping is
    unambiguous. Built once; available_timezones() scans the tzdata directory.
    """
    return {name.lower(): name for name in available_timezones()}


def resolve_timezone(tz_name: str) -> ZoneInfo:
    """
    Resolve an IANA timezone name (e.g. 'America/Los_Angeles') to a ZoneInfo.

    Also accepts the US shorthands in _ZONE_ALIASES ('PT', 'PST', 'PDT', 'ET', ...).
    Matching is case-insensitive and ignores surrounding whitespace, so 'utc', 'UTC',
    'pdt', and 'america/los_angeles' all resolve. Raises ValueError for an unknown name.

    Zone data comes from the OS tzdata in the runtime image; if a future base image
    ships without it, add the `tzdata` package as a dependency.
    """
    cleaned = tz_name.strip()
    canonical = _ZONE_ALIASES.get(cleaned.upper()) or _zones_by_lowercase().get(cleaned.lower())
    if canonical is None:
        raise ValueError(
            f"Unknown timezone '{tz_name}'. Use an IANA name such as 'UTC' or "
            f"'America/Los_Angeles', or a US shorthand such as 'PT'/'PDT' "
            f"(case-insensitive)."
        )
    return ZoneInfo(canonical)


def normalize_to_utc(value: datetime, field_name: str, tz: ZoneInfo | None) -> datetime:
    """
    Convert an inbound query datetime to aware UTC.

    - aware         -> converted to UTC; an explicit offset always wins over `tz`
    - naive + tz    -> read as wall-clock time in `tz`, then converted
    - naive, no tz  -> ValueError

    Naive input is rejected rather than assumed. A datetime with no offset is resolved
    by asyncpg against the *process* timezone, so the same request would mean different
    instants in different environments — and silently return the wrong window rather
    than an error.

    On a DST fall-back ambiguity (2026-11-01 01:30 in America/Los_Angeles happens twice)
    Python's default fold=0 selects the earlier, pre-transition instant.
    """
    if value.tzinfo is not None:
        return value.astimezone(UTC)
    if tz is not None:
        return value.replace(tzinfo=tz).astimezone(UTC)
    raise ValueError(
        f"{field_name} has no timezone. Use an explicit offset (e.g. "
        f"'2026-09-21T02:00:00Z' or '2026-09-20T19:00:00-07:00'), or pass "
        f"tz=<IANA zone> such as tz=America/Los_Angeles to interpret it as local time."
    )


TimeRange = Literal['1H', '6H', '12H', '1D', '2D', '3D', '1W', '1M', '3M']

_TIME_RANGE_DELTAS: dict[str, timedelta] = {
    '1H':  timedelta(hours=1),
    '6H':  timedelta(hours=6),
    '12H': timedelta(hours=12),
    '1D':  timedelta(days=1),
    '2D':  timedelta(days=2),
    '3D':  timedelta(days=3),
    '1W':  timedelta(weeks=1),
    '1M':  timedelta(days=30),
    '3M':  timedelta(days=90),
}


def resolve_time_range(time_range: str) -> tuple[datetime, datetime]:
    """Return (start, end) UTC datetimes for the given time_range token relative to now."""
    delta = _TIME_RANGE_DELTAS.get(time_range)
    if delta is None:
        raise ValueError(
            f"Unknown time_range '{time_range}'. Valid values: {list(_TIME_RANGE_DELTAS)}"
        )
    end = datetime.now(UTC)
    return end - delta, end
