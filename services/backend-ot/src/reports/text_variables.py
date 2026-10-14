"""
Variables in a text block: the site's, and any device's or point's on the site, filled in when the
report is generated.

    {site_name}  {window_start}  ...     a site variable (SITE_VARIABLES)
    {device:12.name}                     a field of device 12 (DEVICE_FIELDS)
    {point:34.name}  {point:34.max}      a field of point 34, or its statistic over the window (POINT_FIELDS)

Devices and points are named by id, so a renamed device still resolves (to its new name). The
builder's Insert menu writes the tokens; the catalog lists the variables (text_variable_catalog).
"""

import re
from collections.abc import Callable
from datetime import datetime

from schemas.reports.api import ReportTextVariable, ReportTextVariables
from schemas.reports.definition import PointStat
from schemas.reports.internal import PointStatValues, ReportSiteContext

TOKEN = re.compile(r"\{([a-z_]+)(?::(\d+)\.([a-z_]+))?\}")
MISSING_VALUE = "—"

SITE_VARIABLES: dict[str, str] = {
    "site_name": "Site name",
    "site_id": "Site id",
    "site_operator": "Site operator",
    "site_capacity": "Site capacity",
    "site_location": "Site city and state",
    "timezone": "Site time zone",
    "window_start": "Period start (site time)",
    "window_end": "Period end (site time)",
}
DEVICE_FIELDS: dict[str, str] = {"name": "Name", "type": "Type", "vendor": "Vendor", "model": "Model"}
POINT_STAT_FIELDS: dict[PointStat, str] = {
    "min": "Minimum in the period",
    "max": "Maximum in the period",
    "avg": "Average in the period",
    "first": "First value in the period",
    "last": "Last value in the period",
    "count": "Number of readings in the period",
}
POINT_FIELDS: dict[str, str] = {"name": "Name", "unit": "Unit", "device": "Its device's name", **POINT_STAT_FIELDS}


def text_variable_catalog() -> ReportTextVariables:
    def listed(variables: dict[str, str]) -> list[ReportTextVariable]:
        return [ReportTextVariable(name=name, description=description) for name, description in variables.items()]

    return ReportTextVariables(site=listed(SITE_VARIABLES), device_fields=listed(DEVICE_FIELDS), point_fields=listed(POINT_FIELDS))


def text_variable_errors(body: str, site: ReportSiteContext) -> list[str]:
    """Every variable in `body` that can't be filled in on this site (typos, ids not on it)."""
    errors: list[str] = []
    for match in TOKEN.finditer(body):
        name, item_id, field = match.group(1), match.group(2), match.group(3)
        token = match.group(0)
        if item_id is None:
            if name not in SITE_VARIABLES:
                errors.append(f"unknown variable {token}")
        elif name == "device":
            if site.find_device(int(item_id)) is None:
                errors.append(f"{token}: device {item_id} is not on this site")
            elif field not in DEVICE_FIELDS:
                errors.append(f"{token}: a device has no '{field}' (use {', '.join(DEVICE_FIELDS)})")
        elif name == "point":
            if site.find_point(int(item_id)) is None:
                errors.append(f"{token}: point {item_id} is not on this site")
            elif field not in POINT_FIELDS:
                errors.append(f"{token}: a point has no '{field}' (use {', '.join(POINT_FIELDS)})")
        else:
            errors.append(f"unknown variable {token}")
    return errors


def stat_point_ids(body: str) -> list[int]:
    """The points whose statistics `body` shows (they are read once, for the whole window)."""
    return sorted({int(match.group(2)) for match in TOKEN.finditer(body)
                   if match.group(1) == "point" and match.group(2) and match.group(3) in POINT_STAT_FIELDS})


def format_number(value: float) -> str:
    """Fewer decimals for bigger numbers, as the report's tables show them: 1,235 · 12.35 · 0.123."""
    magnitude = abs(value)
    decimals = 0 if magnitude >= 100 else 2 if magnitude >= 1 else 3
    text = f"{value:,.{decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def render_text(
    body: str,
    site: ReportSiteContext,
    window_start: datetime,
    window_end: datetime,
    site_timezone: str,
    local_time: Callable[[datetime], str],
    stats: list[PointStatValues],
) -> str:
    """`body` with its variables filled in. A statistic without readings is a dash; a variable that
    can't be filled in (only in definitions saved before a check existed) is left as written."""
    location = site.site.location
    site_values = {
        "site_name": site.site.name,
        "site_id": str(site.site.site_id),
        "site_operator": site.site.operator,
        "site_capacity": site.site.capacity,
        "site_location": f"{location.city}, {location.state}" if location else "",
        "timezone": site_timezone,
        "window_start": local_time(window_start),
        "window_end": local_time(window_end),
    }
    stats_by_point = {entry.point_id: entry.values for entry in stats if entry.bucket_start is None}

    def fill(match: re.Match[str]) -> str:
        name, item_id, field = match.group(1), match.group(2), match.group(3)
        if item_id is None:
            return site_values.get(name, match.group(0))
        if name == "device":
            device = site.find_device(int(item_id))
            if device is None or field not in DEVICE_FIELDS:
                return match.group(0)
            return str(getattr(device, field) or "")
        if name == "point":
            found = site.find_point(int(item_id))
            if found is None or field not in POINT_FIELDS:
                return match.group(0)
            point, device = found
            if field == "name":
                return point.name
            if field == "unit":
                return point.unit or ""
            if field == "device":
                return device.name
            value = stats_by_point.get(point.id, {}).get(field)  # type: ignore[call-overload]
            if field == "count":
                return str(int(value or 0))
            return format_number(value) if value is not None else MISSING_VALUE
        return match.group(0)

    return TOKEN.sub(fill, body)
