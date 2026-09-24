"""Clock settings for registers declared ``type="profile_static"``.

A static register's *value* comes from a frozen table
(``app/timeseries_data/pv_profile_static.py``); this module only answers **what
time it is**, which decides which row of that table a read lands on.

There is no curve here. Values are never computed at read time. The sun curve
lives in ``app/timeseries_data/pv_day_generator.py``, an offline authoring tool
used to *write* the table, not to serve it.

Every function is pure and **nothing here reads the clock** — the timestamp is
passed in, so callers can pin time. The clock is read in exactly one place,
``MockRegisterBlock.getValues``.

Standard library only; this module adds no dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

_MINUTES_PER_DAY = 1440.0
_SECONDS_PER_HOUR = 3600.0
_HOURS_PER_DAY = 24.0


@dataclass(frozen=True)
class ProfileConfig:
    """Clock parameters, built from :class:`~app.settings.Settings`.

    ``timezone_offset_hours`` is a plain offset applied on top of UTC rather
    than a named IANA zone: ``zoneinfo`` needs the ``tzdata`` package on Windows
    and this project takes no dependencies for it. It deliberately has no DST —
    a simulator does not need one.

    ``day_minutes`` is how many real minutes one simulated day takes. The
    default, 1440, is real time; set it low to walk a whole day in seconds.
    """

    timezone_offset_hours: float = 0.0
    day_minutes: float = _MINUTES_PER_DAY


def simulated_hour_of_day(now: datetime, config: ProfileConfig) -> float:
    """Hour of the simulated day in ``[0, 24)``.

    Derived from elapsed epoch seconds rather than ``now.hour`` so that time
    compression needs no special case: at ``day_minutes == 1440`` the
    acceleration is exactly 1.0 and this reduces to UTC hour-of-day plus the
    configured offset. POSIX timestamps ignore leap seconds, so every day is
    exactly 86400 s and that reduction is exact, not approximate.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    offset_seconds = now.timestamp() + config.timezone_offset_hours * _SECONDS_PER_HOUR
    acceleration = _MINUTES_PER_DAY / config.day_minutes
    return (offset_seconds * acceleration / _SECONDS_PER_HOUR) % _HOURS_PER_DAY
