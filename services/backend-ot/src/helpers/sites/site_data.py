"""Site helper functions for comprehensive DB reads."""


from sqlalchemy import select

from db.connection import get_async_session_factory
from logger import get_logger
from schemas.api_models import (
    Coordinates,
    DevicePointResponse,
    DevicePointsCategoryGrouped,
    DeviceWithPoints,
    Location,
    SiteComprehensiveResponse,
)
from schemas.api_models.requests import DeviceScanRanges
from schemas.db_models.orm_models import Device, DevicePoint, Site

logger = get_logger(__name__)


async def get_complete_site_data_with_points(site_id: int) -> SiteComprehensiveResponse | None:
    """
    Get a site with devices and their categorized device points.
    Used by the API's comprehensive site endpoint and the scheduler/poller.
    """
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        site_result = await session.execute(select(Site).where(Site.id == site_id))
        site = site_result.scalar_one_or_none()
        if site is None:
            return None

        device_result = await session.execute(
            select(Device).where(Device.site_id == site_id).order_by(Device.device_id)
        )
        devices = device_result.scalars().all()
        device_ids = [d.device_id for d in devices]

        points_by_device: dict[int, list[DevicePointResponse]] = {}
        if device_ids:
            points_result = await session.execute(
                select(DevicePoint).where(
                    DevicePoint.device_id.in_(device_ids),
                    DevicePoint.site_id == site_id,
                )
            )
            for dp in points_result.scalars().all():
                points_by_device.setdefault(dp.device_id, []).append(
                    DevicePointResponse.model_validate(dp, from_attributes=True)
                )

        coordinates, location = _build_coordinates_and_location(site)

        device_items: list[DeviceWithPoints] = []
        for device in devices:
            raw_points = points_by_device.get(device.device_id, [])
            categorized_points = DevicePointsCategoryGrouped(
                native=[p for p in raw_points if p.category == "NATIVE"],
                standardized=[p for p in raw_points if p.category == "STANDARDIZED"],
                virtual=[p for p in raw_points if p.category == "VIRTUAL"],
            )
            device_items.append(DeviceWithPoints(**_device_base_kwargs(device), points=categorized_points))

        return SiteComprehensiveResponse(
            **_site_base_kwargs(site, coordinates, location),
            devices=device_items,
        )


# --- Private helpers ---

def _build_coordinates_and_location(site):
    coordinates = None
    if site.coordinates:
        coordinates = Coordinates(lat=site.coordinates["lat"], lng=site.coordinates["lng"])
    location = None
    if site.location:
        location = Location(**site.location)
    return coordinates, location


def _site_base_kwargs(site, coordinates, location) -> dict:
    return {
        "site_id": site.id,
        "client_id": site.client_id,
        "name": site.name,
        "location": location,
        "operator": site.operator,
        "capacity": site.capacity,
        "device_count": site.device_count,
        "description": site.description,
        "coordinates": coordinates,
        "created_at": site.created_at,
        "updated_at": site.updated_at,
        "last_update": site.last_update,
    }


def _device_base_kwargs(device) -> dict:
    scan_ranges = None
    if device.scan_ranges:
        scan_ranges = DeviceScanRanges.model_validate(device.scan_ranges)
    return {
        "device_id": device.device_id,
        "site_id": device.site_id,
        "name": device.name,
        "type": device.type,
        "vendor": device.vendor,
        "model": device.model,
        "host": device.host,
        "port": device.port,
        "timeout": device.timeout,
        "server_address": device.server_address,
        "description": device.description,
        "poll_enabled": device.poll_enabled if device.poll_enabled is not None else True,
        "read_from_aggregator": device.read_from_aggregator if device.read_from_aggregator is not None else True,
        "protocol": device.protocol,
        "created_at": device.created_at,
        "updated_at": device.updated_at,
        "scan_ranges": scan_ranges,
        "scan_ranges_locked": device.scan_ranges_locked or False,
        "modbus_address_mode": device.modbus_address_mode,
    }
