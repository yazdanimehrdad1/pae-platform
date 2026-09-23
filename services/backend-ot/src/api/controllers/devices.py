"""
Devices controller.

Sits between the router and db.devices.
No cache layer — all reads and writes go directly to the DB.
"""

from typing import Literal

import db.devices as devices_db
from helpers.device_points.device_points_crud import create_device_points
from helpers.device_points.device_standardized_points import generate_standardized_points
from logger import get_logger
from schemas.api_models import (
    DeviceCreateRequest,
    DeviceListItem,
    DeviceUpdate,
    DeviceWithPoints,
)
from utils.exceptions import NotFoundError

logger = get_logger(__name__)


async def get_all_devices(site_id: int, include_deleted: bool = False) -> list[DeviceWithPoints]:
    return await devices_db.get_all_devices(site_id, include_deleted=include_deleted)


async def get_device_by_id(site_id: int, device_id: int, include_deleted: bool = False) -> DeviceWithPoints:
    device = await devices_db.get_device_by_id(device_id, site_id, include_deleted=include_deleted)
    if device is None:
        raise NotFoundError(f"Device with ID {device_id} not found in site {site_id}")
    return device


async def create_device(device: DeviceCreateRequest, site_id: int) -> DeviceWithPoints:
    created = await devices_db.create_device(device, site_id=site_id)
    standardized = generate_standardized_points(device.type, created.device_id, site_id)
    if standardized:
        await create_device_points(standardized)
    return created


async def update_device(
    device_id: int, device_update: DeviceUpdate, site_id: int
) -> DeviceWithPoints:
    return await devices_db.update_device(device_id, device_update, site_id=site_id)


async def delete_device(
    device_id: int,
    site_id: int,
    mode: Literal["soft", "hard"] = "soft",
    confirm: bool = False,
) -> DeviceListItem | None:
    return await devices_db.delete_device(device_id, site_id=site_id, mode=mode, confirm=confirm)


async def restore_device(device_id: int, site_id: int) -> DeviceWithPoints:
    device = await devices_db.restore_device(device_id, site_id=site_id)
    if device is None:
        raise NotFoundError(f"Device with ID {device_id} not found in site {site_id}")
    return device
