"""
Site health (GET /api/sites/{site_id}/health): the ALARM-class points that are set, per device.

Loads the site's devices, reads the latest value of every ALARM point to evaluate (one query,
virtual points computed), and rolls the set points up per device and for the site.
"""

from datetime import UTC, datetime

import db.devices as devices_db
import db.sites as sites_db
from helpers.reads.device_points_readings import get_latest_readings_by_point_ids
from helpers.sites.site_health import (
    SEVERITY_ORDER,
    alarm_points,
    device_alarm_status,
    site_alarm_counts,
)
from schemas.api_models import DeviceWithPoints, Severity, SiteHealthResponse
from utils.exceptions import NotFoundError


def _select_devices(
    site_id: int, devices: list[DeviceWithPoints], device_ids: list[int] | None
) -> list[DeviceWithPoints]:
    """All the site's devices when no ids are given; otherwise those, each of which must be a
    device of this site."""
    if not device_ids:
        return devices
    device_by_id = {device.device_id: device for device in devices}
    missing = sorted(set(device_ids) - device_by_id.keys())
    if missing:
        raise NotFoundError(f"Devices {missing} not found in site {site_id}")
    return [device_by_id[device_id] for device_id in sorted(set(device_ids))]


async def get_site_health(
    site_id: int,
    severities: list[Severity] | None = None,
    device_ids: list[int] | None = None,
) -> SiteHealthResponse:
    """The set ALARM points of the site's devices. No severities means all (including points
    without a severity); no device ids means all of the site's devices."""
    site = await sites_db.get_site_by_id(site_id)
    if site is None:
        raise NotFoundError(f"Site with id {site_id} not found")

    severity_filter = sorted(set(severities), key=SEVERITY_ORDER.index) if severities else None
    device_ids_filter = sorted(set(device_ids)) if device_ids else None
    devices = _select_devices(site_id, await devices_db.get_all_devices(site_id), device_ids_filter)

    point_ids = sorted({point.id for device in devices for point in alarm_points(device, severity_filter)})
    readings = await get_latest_readings_by_point_ids(point_ids, site_id=site_id) if point_ids else []
    readings_by_point = {reading.device_point_id: reading for reading in readings}

    statuses = [device_alarm_status(device, readings_by_point, severity_filter) for device in devices]
    return SiteHealthResponse(
        site_id=site_id,
        generated_at=datetime.now(UTC),
        severity_filter=severity_filter,
        device_ids_filter=device_ids_filter,
        devices=statuses,
        **site_alarm_counts(statuses).model_dump(),
    )
