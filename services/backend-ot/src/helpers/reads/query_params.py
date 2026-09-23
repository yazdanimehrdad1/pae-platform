"""
Query-parameter helpers for the readings endpoints.

Parses and validates the raw query string into values the read layer can use, and
translates the resulting validation errors into 422s so the routers stay thin. The
timezone rules themselves live in `helpers.common.date_time`; this module only adapts
them to HTTP.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Query, status

from helpers.common.date_time import normalize_to_utc, resolve_timezone

TZ_QUERY = Query(
    None,
    description=(
        "IANA timezone, e.g. 'America/Los_Angeles', or a US shorthand such as 'PT'/'PDT'. "
        "Interprets naive start_time/end_time and renders response timestamps in this zone. "
        "An explicit offset on a timestamp takes precedence over this."
    ),
)


def parse_point_ids(raw: str | None) -> list[int]:
    """Parse a comma-separated device_point_id list; an empty value means 'all points'."""
    if not raw:
        return []
    try:
        return [int(p.strip()) for p in raw.split(",") if p.strip()]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="point_ids must be a comma-separated list of integers (e.g. '1,2,3')",
        ) from None


def resolve_display_tz(tz: str | None) -> ZoneInfo | None:
    """Resolve the tz query param, translating an unknown zone into a 422."""
    if not tz:
        return None
    try:
        return resolve_timezone(tz)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err


def normalize_bound(value: datetime | None, field_name: str, tz: ZoneInfo | None) -> datetime | None:
    """Convert a query bound to aware UTC, translating naive-without-tz into a 422."""
    if value is None:
        return None
    try:
        return normalize_to_utc(value, field_name, tz)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err


def in_display_tz(value: datetime | None, tz: ZoneInfo | None) -> datetime | None:
    """Render an aware UTC datetime in the requested zone. Same instant, different offset."""
    if value is None or tz is None:
        return value
    return value.astimezone(tz)
