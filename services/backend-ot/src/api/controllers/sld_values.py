"""
Live values for a site's SLD info boxes (GET /api/sites/{site_id}/sld/values).

Resolves every element linked to a device: the latest reading of each mapped point (one query,
virtual points computed), shaped per role, plus the device health the site profile declares for
the element's type.
"""

from datetime import UTC, datetime

import db.devices as devices_db
import db.site_slds as site_slds_db
import db.sites as sites_db
from helpers.reads.device_points_readings import get_latest_readings_by_point_ids
from helpers.sites.sld import node_role_values
from schemas.api_models import (
    DeviceHealth,
    DeviceWithPoints,
    SiteResponse,
    SldNode,
    SldNodeValues,
    SldValuesResponse,
)
from schemas.site_profiles import DeviceHealthContext
from site_profiles.profile_registry import get_site_profile
from utils.exceptions import NotFoundError, SiteSldNotFoundError


async def _node_health(
    node: SldNode, site: SiteResponse, devices: list[DeviceWithPoints], device: DeviceWithPoints | None, now: datetime
) -> DeviceHealth | None:
    """The profile's verdict for the node's device; None when the type shows no health or the site
    declares no check for it. A device that no longer exists is unknown."""
    if site.profile is None:
        return None
    check = get_site_profile(site.profile).find_health_check(node.type)
    if check is None:
        return None
    if device is None:
        return DeviceHealth(healthy=None, reason="The linked device no longer exists")
    return await check.evaluate(DeviceHealthContext(site=site, devices=devices, device=device, now=now))


async def get_sld_values(site_id: int) -> SldValuesResponse:
    site = await sites_db.get_site_by_id(site_id)
    if site is None:
        raise NotFoundError(f"Site with id {site_id} not found")
    stored = await site_slds_db.get_site_sld(site_id)
    if stored is None:
        raise SiteSldNotFoundError(f"Site {site_id} has no single line diagram")

    devices = await devices_db.get_all_devices(site_id)
    device_by_id = {device.device_id: device for device in devices}
    links = [(node, node.device) for node in stored.sld.nodes if node.device is not None]

    # Only points that still exist on a live device of this site; anything else reads as not available.
    live_point_ids = {
        point.id
        for device in devices
        for point in device.points.standardized + device.points.native + device.points.virtual
    }
    point_ids = sorted({point_id for _, link in links for point_id in link.points.values()} & live_point_ids)
    readings = await get_latest_readings_by_point_ids(point_ids, site_id=site_id) if point_ids else []
    readings_by_point = {reading.device_point_id: reading for reading in readings}

    now = datetime.now(UTC)
    nodes: list[SldNodeValues] = []
    for node, link in links:
        device = device_by_id.get(link.device_id)
        nodes.append(
            SldNodeValues(
                node_id=node.id,
                device_id=link.device_id,
                values=node_role_values(node, readings_by_point),
                health=await _node_health(node, site, devices, device, now),
            )
        )
    return SldValuesResponse(site_id=site_id, sld_revision=stored.revision, generated_at=now, nodes=nodes)
