"""
Device database operations.

Handles CRUD operations for devices table.
Uses SQLAlchemy 2.0+ async ORM.
"""

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.connection import get_async_session_factory
from logger import get_logger
from schemas.api_models import (
    DeviceCreateRequest,
    DeviceListItem,
    DevicePointResponse,
    DevicePoints,
    DeviceUpdate,
    DeviceWithPoints,
)
from schemas.api_models.requests import DeviceScanRanges
from schemas.db_models.orm_models import Device, DevicePoint, Site
from utils.exceptions import (
    AppError,
    ConflictError,
    InternalError,
    NotFoundError,
    ValidationError,
)

logger = get_logger(__name__)


def _orm_scan_ranges(device: Device) -> DeviceScanRanges | None:
    if device.scan_ranges:
        return DeviceScanRanges.model_validate(device.scan_ranges)
    return None


def _group_points(orm_points) -> DevicePoints:
    grouped = DevicePoints()
    for pt in orm_points:
        point = DevicePointResponse.model_validate(pt, from_attributes=True)
        if pt.category == "STANDARDIZED":
            grouped.standardized.append(point)
        elif pt.category == "NATIVE":
            grouped.native.append(point)
        elif pt.category == "VIRTUAL":
            grouped.virtual.append(point)
    return grouped


def _device_to_with_points(device: Device, points: DevicePoints) -> DeviceWithPoints:
    return DeviceWithPoints(
        device_id=device.device_id,
        site_id=device.site_id,
        name=device.name,
        type=device.type,
        vendor=device.vendor,
        model=device.model,
        host=device.host,
        port=device.port,
        timeout=device.timeout,
        server_address=device.server_address,
        description=device.description,
        poll_enabled=device.poll_enabled if device.poll_enabled is not None else True,
        read_from_aggregator=device.read_from_aggregator if device.read_from_aggregator is not None else True,
        protocol=device.protocol,
        created_at=device.created_at,
        updated_at=device.updated_at,
        deleted_at=device.deleted_at,
        scan_ranges=_orm_scan_ranges(device),
        scan_ranges_locked=device.scan_ranges_locked or False,
        modbus_address_mode=device.modbus_address_mode,
        points=points,
    )


async def create_device(device: DeviceCreateRequest, site_id: int) -> DeviceWithPoints:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            site_result = await session.execute(
                select(Site).where(Site.id == site_id, Site.deleted_at.is_(None))
            )
            if site_result.scalar_one_or_none() is None:
                raise NotFoundError(f"Site with id '{site_id}' not found")

            # Check for active device with same name
            existing = await session.execute(
                select(Device).where(
                    Device.name == device.name,
                    Device.site_id == site_id,
                    Device.deleted_at.is_(None),
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ConflictError(f"Device with name '{device.name}' already exists in site {site_id}")

            # Check for soft-deleted device with same name — suggest restore
            soft_deleted = await session.execute(
                select(Device).where(
                    Device.name == device.name,
                    Device.site_id == site_id,
                    Device.deleted_at.is_not(None),
                )
            )
            sd = soft_deleted.scalar_one_or_none()
            if sd is not None:
                raise ConflictError(
                    f"A soft-deleted device named '{device.name}' exists in site {site_id} "
                    f"(device_id={sd.device_id}). "
                    f"Use POST /devices/site/{site_id}/devices/{sd.device_id}/restore to restore it."
                )

            new_device = Device(
                name=device.name,
                type=device.type,
                vendor=device.vendor,
                model=device.model,
                host=device.host,
                port=device.port,
                timeout=device.timeout,
                server_address=device.server_address,
                description=device.description,
                poll_enabled=device.poll_enabled,
                read_from_aggregator=device.read_from_aggregator,
                modbus_address_mode=device.modbus_address_mode,
                protocol=device.protocol,
                site_id=site_id,
            )

            session.add(new_device)
            await session.flush()
            device_primary_key = new_device.device_id
            logger.info(f"Created device: {device.name} (ID: {device_primary_key})")
            await session.commit()

            result = await session.execute(
                select(Device).where(Device.device_id == device_primary_key)
            )
            created_device = result.scalar_one_or_none()
            if created_device is None:
                raise InternalError(f"Device with id {device_primary_key} not found after creation")

            return _device_to_with_points(created_device, DevicePoints())

        except IntegrityError as e:
            await session.rollback()
            error_text = str(e).lower()
            if "unique" in error_text or "duplicate" in error_text or "already exists" in error_text:
                logger.warning(f"Device name '{device.name}' already exists in site {site_id}")
                raise ConflictError(f"Device with name '{device.name}' already exists in site {site_id}") from e
            else:
                logger.error(f"Database integrity error creating device: {e}")
                raise ValidationError(f"Database integrity error: {e}") from e
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error creating device: {e}")
            raise


async def get_all_devices(site_id: int, include_deleted: bool = False) -> list[DeviceWithPoints]:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        query = select(Device).where(Device.site_id == site_id)
        if not include_deleted:
            query = query.where(Device.deleted_at.is_(None))
        result = await session.execute(query.order_by(Device.device_id))
        devices = result.scalars().all()

        device_ids = [device.device_id for device in devices]
        points_by_device: dict[int, DevicePoints] = {}
        if device_ids:
            points_query = select(DevicePoint).where(DevicePoint.device_id.in_(device_ids))
            if not include_deleted:
                points_query = points_query.where(DevicePoint.deleted_at.is_(None))
            points_result = await session.execute(points_query)
            for pt in points_result.scalars().all():
                if pt.device_id not in points_by_device:
                    points_by_device[pt.device_id] = DevicePoints()
                point = DevicePointResponse.model_validate(pt, from_attributes=True)
                grouped = points_by_device[pt.device_id]
                if pt.category == "STANDARDIZED":
                    grouped.standardized.append(point)
                elif pt.category == "NATIVE":
                    grouped.native.append(point)
                elif pt.category == "VIRTUAL":
                    grouped.virtual.append(point)

        return [
            _device_to_with_points(device, points_by_device.get(device.device_id, DevicePoints()))
            for device in devices
        ]


async def get_device_by_id(
    device_id: int, site_id: int, include_deleted: bool = False
) -> DeviceWithPoints | None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        query = select(Device).where(Device.device_id == device_id, Device.site_id == site_id)
        if not include_deleted:
            query = query.where(Device.deleted_at.is_(None))
        result = await session.execute(query)
        device = result.scalar_one_or_none()

        if device is None:
            return None

        points_query = select(DevicePoint).where(DevicePoint.device_id == device.device_id)
        if not include_deleted:
            points_query = points_query.where(DevicePoint.deleted_at.is_(None))
        points_result = await session.execute(points_query)
        device_points = _group_points(points_result.scalars().all())

        return _device_to_with_points(device, device_points)


async def update_device(device_id: int, device_update: DeviceUpdate, site_id: int) -> DeviceWithPoints:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            result = await session.execute(
                select(Device).where(
                    Device.device_id == device_id,
                    Device.site_id == site_id,
                    Device.deleted_at.is_(None),
                )
            )
            device = result.scalar_one_or_none()

            if device is None:
                raise NotFoundError(f"Device with id {device_id} not found")

            if device_update.name is not None:
                device.name = device_update.name
            if device_update.type is not None:
                device.type = device_update.type
            if device_update.vendor is not None:
                device.vendor = device_update.vendor
            if device_update.model is not None:
                device.model = device_update.model
            if device_update.host is not None:
                device.host = device_update.host
            if device_update.port is not None:
                device.port = device_update.port
            if device_update.timeout is not None:
                device.timeout = device_update.timeout
            if device_update.server_address is not None:
                device.server_address = device_update.server_address
            if device_update.description is not None:
                device.description = device_update.description
            if device_update.poll_enabled is not None:
                device.poll_enabled = device_update.poll_enabled
            if device_update.read_from_aggregator is not None:
                device.read_from_aggregator = device_update.read_from_aggregator
            if device_update.protocol is not None:
                device.protocol = device_update.protocol
            if device_update.modbus_address_mode is not None:
                device.modbus_address_mode = device_update.modbus_address_mode

            await session.commit()
            await session.refresh(device)
            logger.info(f"Updated device with id {device.device_id}")

            points_result = await session.execute(
                select(DevicePoint).where(
                    DevicePoint.device_id == device.device_id,
                    DevicePoint.deleted_at.is_(None),
                )
            )
            return _device_to_with_points(device, _group_points(points_result.scalars().all()))

        except IntegrityError as e:
            await session.rollback()
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                logger.warning(f"Device name already exists in site {site_id}")
                raise ConflictError(f"Device with this name already exists in site {site_id}") from e
            else:
                logger.error(f"Database integrity error updating device: {e}")
                raise ValidationError(f"Database integrity error: {e}") from e
        except AppError:
            # Our own NotFound/Conflict errors carry the right status; don't wrap them as 500.
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error updating device: {e}")
            raise InternalError(f"Failed to update device: {e}") from e


async def delete_device(
    device_id: int,
    site_id: int,
    mode: Literal["soft", "hard"] = "soft",
    confirm: bool = False,
) -> DeviceListItem | None:
    if mode == "hard" and not confirm:
        raise ValidationError("Set confirm=true to permanently delete a device and all its data")

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id, Device.site_id == site_id)
            )
            device = result.scalar_one_or_none()

            if device is None:
                logger.warning(f"Device with id {device_id} not found for deletion")
                return None

            device_response = DeviceListItem(
                device_id=device.device_id,
                site_id=device.site_id,
                name=device.name,
                type=device.type,
                vendor=device.vendor,
                model=device.model,
                host=device.host,
                port=device.port,
                timeout=device.timeout,
                server_address=device.server_address,
                description=device.description,
                poll_enabled=device.poll_enabled if device.poll_enabled is not None else True,
                read_from_aggregator=device.read_from_aggregator if device.read_from_aggregator is not None else True,
                protocol=device.protocol,
                created_at=device.created_at,
                updated_at=device.updated_at,
                deleted_at=device.deleted_at,
                scan_ranges=_orm_scan_ranges(device),
                scan_ranges_locked=device.scan_ranges_locked or False,
                modbus_address_mode=device.modbus_address_mode,
            )

            if mode == "soft":
                now = datetime.now(UTC)
                device.deleted_at = now
                device_response.deleted_at = now
                # Cascade soft-delete all active DevicePoints
                points_result = await session.execute(
                    select(DevicePoint).where(
                        DevicePoint.device_id == device_id,
                        DevicePoint.deleted_at.is_(None),
                    )
                )
                for pt in points_result.scalars().all():
                    pt.deleted_at = now
                await session.commit()
                logger.info(f"Soft-deleted device {device_id} and its active points")
            else:
                await session.delete(device)
                await session.flush()
                await session.commit()
                logger.info(f"Hard-deleted device '{device.name}' (id={device_id})")

            return device_response

        except Exception as e:
            await session.rollback()
            logger.error(f"Database error deleting device: {e}")
            raise InternalError(f"Failed to delete device: {e}") from e


async def restore_device(device_id: int, site_id: int) -> DeviceWithPoints | None:
    """Restore a soft-deleted device and all its soft-deleted DevicePoints."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            result = await session.execute(
                select(Device).where(Device.device_id == device_id, Device.site_id == site_id)
            )
            device = result.scalar_one_or_none()

            if device is None:
                return None
            if device.deleted_at is None:
                raise ConflictError(f"Device {device_id} is not soft-deleted")

            device.deleted_at = None

            points_result = await session.execute(
                select(DevicePoint).where(
                    DevicePoint.device_id == device_id,
                    DevicePoint.deleted_at.is_not(None),
                )
            )
            for pt in points_result.scalars().all():
                pt.deleted_at = None

            await session.commit()
            logger.info(f"Restored device {device_id} and its points")

        except AppError:
            # Our own NotFound/Conflict errors carry the right status; don't wrap them as 500.
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error restoring device: {e}")
            raise InternalError(f"Failed to restore device: {e}") from e

    return await get_device_by_id(device_id, site_id)


async def lock_device_scan_ranges(device_id: int, ranges: DeviceScanRanges) -> None:
    """Store manually-specified scan ranges and set scan_ranges_locked = True."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalar_one_or_none()
        if device is None:
            raise NotFoundError(f"Device {device_id} not found")
        device.scan_ranges = ranges.model_dump()
        device.scan_ranges_locked = True
        await session.commit()


async def reset_device_scan_ranges(device_id: int) -> DeviceScanRanges:
    """Clear the lock and recompute scan ranges from current NATIVE points."""
    from helpers.device_points.scan_range_computation import compute_device_scan_ranges

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalar_one_or_none()
        if device is None:
            raise NotFoundError(f"Device {device_id} not found")

        points_result = await session.execute(
            select(DevicePoint).where(
                DevicePoint.device_id == device_id,
                DevicePoint.category == "NATIVE",
                DevicePoint.deleted_at.is_(None),
            )
        )
        native_points = [
            DevicePointResponse.model_validate(p, from_attributes=True)
            for p in points_result.scalars().all()
        ]
        ranges = compute_device_scan_ranges(native_points)
        device.scan_ranges = ranges.model_dump()
        device.scan_ranges_locked = False
        await session.commit()
        return ranges
