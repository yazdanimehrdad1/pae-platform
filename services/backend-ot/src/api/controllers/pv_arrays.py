"""
PV array config controller.

Sits between the routers and db.pv_arrays. A config belongs to an active PV or INVERTER
device of the site in the path.
"""

import db.devices as devices_db
import db.pv_arrays as pv_arrays_db
import db.sites as sites_db
from schemas.api_models import PvArrayConfigResponse, PvArrayConfigUpsertRequest
from utils.exceptions import NotFoundError, ValidationError

PV_ARRAY_DEVICE_TYPES = frozenset({"PV", "INVERTER"})


async def get_site_pv_arrays(site_id: int) -> list[PvArrayConfigResponse]:
    """The site's PV arrays (404 if the site doesn't exist; [] if it has none)."""
    if await sites_db.get_site_by_id(site_id) is None:
        raise NotFoundError(f"Site with id {site_id} not found")
    return await pv_arrays_db.get_site_pv_arrays(site_id)


async def _require_pv_device(site_id: int, device_id: int) -> None:
    device = await devices_db.get_device_by_id(device_id, site_id)
    if device is None:
        raise NotFoundError(f"Device with ID {device_id} not found in site {site_id}")
    if device.type not in PV_ARRAY_DEVICE_TYPES:
        raise ValidationError(
            f"Device {device_id} is a {device.type} device; a PV array belongs to a PV or INVERTER device",
            payload={"device_type": device.type},
        )


async def get_device_pv_array(site_id: int, device_id: int) -> PvArrayConfigResponse:
    await _require_pv_device(site_id, device_id)
    config = await pv_arrays_db.get_device_pv_array(device_id)
    if config is None:
        raise NotFoundError(f"Device {device_id} has no PV array config")
    return config


async def put_device_pv_array(
    site_id: int, device_id: int, config: PvArrayConfigUpsertRequest
) -> PvArrayConfigResponse:
    """Create or replace the device's PV array config."""
    await _require_pv_device(site_id, device_id)
    return await pv_arrays_db.upsert_device_pv_array(device_id, config)


async def delete_device_pv_array(site_id: int, device_id: int) -> PvArrayConfigResponse:
    """Delete the device's PV array config and return it (404 if it had none)."""
    await _require_pv_device(site_id, device_id)
    deleted = await pv_arrays_db.delete_device_pv_array(device_id)
    if deleted is None:
        raise NotFoundError(f"Device {device_id} has no PV array config")
    return deleted
