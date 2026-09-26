"""Device points CRUD operations."""

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select

from db.connection import get_async_session_factory
from helpers.device_points.address_overlap import NativePointRange, validate_no_register_overlap
from helpers.device_points.scan_range_computation import compute_device_scan_ranges
from schemas.api_models import SUPPORTED_DATA_TYPES, DataType, DevicePointData, register_size
from schemas.api_models.requests import DevicePointsBulkRequest, DevicePointUpdateRequest
from schemas.api_models.responses import DevicePointResponse
from schemas.db_models.orm_models import Device, DevicePoint
from utils.exceptions import ConflictError, InternalError, NotFoundError, ValidationError


async def _recompute_scan_ranges(session, device_id: int) -> None:
    """Recompute and persist scan ranges unless device is locked. Must be called inside an open session before commit."""
    device_result = await session.execute(select(Device).where(Device.device_id == device_id))
    device = device_result.scalar_one_or_none()
    if device is None or device.scan_ranges_locked:
        return

    points_result = await session.execute(
        select(DevicePoint).where(
            DevicePoint.device_id == device_id,
            DevicePoint.category == "NATIVE",
            DevicePoint.deleted_at.is_(None),
        )
    )
    native_responses = [
        DevicePointResponse.model_validate(p, from_attributes=True)
        for p in points_result.scalars().all()
    ]
    ranges = compute_device_scan_ranges(native_responses)
    device.scan_ranges = ranges.model_dump()


async def create_device_points(device_points_list: list[DevicePointData]) -> bool:
    """
    Persist a list of DevicePointData to the database.
    Uniqueness is guaranteed by the caller (validate_device_points_uniqueness).
    """
    if not device_points_list:
        return True
    try:
        session_factory = get_async_session_factory()
        async with session_factory() as session:
            new_points = [DevicePoint(**point.model_dump()) for point in device_points_list]
            session.add_all(new_points)
            await session.commit()
        return True
    except Exception as e:
        raise InternalError(f"Failed to create device points: {str(e)}") from e


async def get_device_points(
    device_id: int,
    category: str | None = None,
    include_deleted: bool = False,
    point_class: str | None = None,
    severity: str | None = None,
) -> list[DevicePoint]:
    """Get all points for a specific device, optionally filtered by category, class and severity."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        query = (
            select(DevicePoint)
            .where(DevicePoint.device_id == device_id)
            .order_by(DevicePoint.address.asc())
        )
        if category is not None:
            query = query.where(DevicePoint.category == category.upper())
        if point_class is not None:
            query = query.where(DevicePoint.point_class == point_class.upper())
        if severity is not None:
            query = query.where(DevicePoint.severity == severity.upper())
        if not include_deleted:
            query = query.where(DevicePoint.deleted_at.is_(None))
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_deleted_device_points(device_id: int) -> list[DevicePoint]:
    """Get only soft-deleted points for a specific device."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(DevicePoint)
            .where(DevicePoint.device_id == device_id, DevicePoint.deleted_at.is_not(None))
            .order_by(DevicePoint.deleted_at.desc())
        )
        return list(result.scalars().all())


async def update_device_point(
    point_id: int, data: DevicePointUpdateRequest
) -> DevicePoint:
    """Update a device point and trigger scan range recompute."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(DevicePoint).where(DevicePoint.id == point_id))
        point = result.scalar_one_or_none()
        if point is None:
            raise NotFoundError(f"Device point {point_id} not found")

        if data.name is not None:
            existing = await session.execute(
                select(DevicePoint).where(
                    DevicePoint.device_id == point.device_id,
                    DevicePoint.name == data.name,
                    DevicePoint.id != point_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ConflictError(f"A point named '{data.name}' already exists on device {point.device_id}")
            point.name = data.name

        if point.category == "NATIVE" and any(
            getattr(data, f) is not None for f in ("address", "size", "poll_kind")
        ):
            eff_poll_kind = data.poll_kind if data.poll_kind is not None else point.poll_kind
            eff_address = data.address if data.address is not None else point.address
            eff_size = data.size if data.size is not None else point.size
            others_result = await session.execute(
                select(DevicePoint).where(
                    DevicePoint.device_id == point.device_id,
                    DevicePoint.category == "NATIVE",
                    DevicePoint.deleted_at.is_(None),
                    DevicePoint.id != point_id,
                )
            )
            native_candidates = [
                NativePointRange(name=p.name, poll_kind=p.poll_kind, address=p.address, size=p.size)
                for p in others_result.scalars().all()
            ]
            native_candidates.append(
                NativePointRange(name=point.name, poll_kind=eff_poll_kind, address=eff_address, size=eff_size)
            )
            # Ensures the updated point's register range doesn't collide with any other
            # active NATIVE point on this device within the same poll_kind address space.
            validate_no_register_overlap(native_candidates)

        # Enforce size <-> data_type consistency against the effective (post-patch) values.
        # The request validator only catches the case where both are supplied together.
        eff_data_type = data.data_type if data.data_type is not None else point.data_type
        eff_size_val = data.size if data.size is not None else point.size
        if eff_data_type in SUPPORTED_DATA_TYPES:
            expected_size = register_size(cast(DataType, eff_data_type))
            if eff_size_val != expected_size:
                raise ValidationError(
                    f"data_type '{eff_data_type}' requires size={expected_size}, got size={eff_size_val}"
                )

        if data.poll_kind is not None:
            point.poll_kind = data.poll_kind
        if data.address is not None:
            point.address = data.address
        if data.size is not None:
            point.size = data.size
        if data.data_type is not None:
            point.data_type = data.data_type
        if data.scale_factor is not None:
            point.scale_factor = data.scale_factor
        if data.unit is not None:
            point.unit = data.unit
        if data.byte_order is not None:
            point.byte_order = data.byte_order
        if data.word_order is not None:
            point.word_order = data.word_order
        if data.bitfield_detail is not None:
            point.bitfield_detail = data.bitfield_detail
        if data.enum_detail is not None:
            point.enum_detail = data.enum_detail
        if data.point_class is not None:
            point.point_class = data.point_class
        if data.severity is not None:
            point.severity = data.severity

        device_id = point.device_id
        await _recompute_scan_ranges(session, device_id)
        await session.commit()
        await session.refresh(point)
        return point


async def delete_device_points(
    device_id: int, point_ids: list[int], hard: bool = False
) -> tuple[list[int], list[DevicePoint]]:
    """
    Delete or soft-delete multiple device points in one transaction.
    hard=False: sets deleted_at (readings preserved).
    hard=True: permanently removes points and cascades to readings.
    Returns (missing_ids, deleted_points).
    For hard deletes the returned points reflect state just before removal.
    """
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(DevicePoint).where(
                DevicePoint.device_id == device_id,
                DevicePoint.id.in_(point_ids),
                DevicePoint.deleted_at.is_(None),
            )
        )
        found = {p.id: p for p in result.scalars().all()}
        missing = [pid for pid in point_ids if pid not in found]

        if hard:
            deleted = list(found.values())
            for point in deleted:
                await session.delete(point)
            await session.flush()
            await _recompute_scan_ranges(session, device_id)
            await session.commit()
        else:
            now = datetime.now(UTC)
            for point in found.values():
                point.deleted_at = now
            await session.flush()
            await _recompute_scan_ranges(session, device_id)
            await session.commit()
            deleted = []
            for point in found.values():
                await session.refresh(point)
                deleted.append(point)

        return missing, deleted


async def restore_device_point(point_id: int) -> DevicePoint:
    """Clear deleted_at on a soft-deleted point and recompute scan ranges."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(DevicePoint).where(DevicePoint.id == point_id))
        point = result.scalar_one_or_none()
        if point is None:
            raise NotFoundError(f"Device point {point_id} not found")

        point.deleted_at = None
        await session.flush()
        await _recompute_scan_ranges(session, point.device_id)
        await session.commit()
        await session.refresh(point)
        return point


async def bulk_upsert_device_points(
    site_id: int, device_id: int, bulk: DevicePointsBulkRequest
) -> list[DevicePoint]:
    """
    Upsert multiple device points in one transaction.
    Points are matched by name: existing names are updated, new names are created.
    Scan range recompute runs once at the end.
    """
    for point in bulk.points:
        if point.category == "NATIVE":
            if point.poll_kind is None:
                raise ValidationError(f"poll_kind is required for NATIVE point '{point.name}'")
            if point.address is None:
                raise ValidationError(f"address is required for NATIVE point '{point.name}'")

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        existing_result = await session.execute(
            select(DevicePoint).where(DevicePoint.device_id == device_id)
        )
        existing_by_name: dict[str, DevicePoint] = {
            p.name: p for p in existing_result.scalars().all()
        }

        incoming_names = {data.name for data in bulk.points}
        # Only active, untouched points count as "occupied" for overlap validation
        native_candidates = [
            NativePointRange(name=p.name, poll_kind=p.poll_kind, address=p.address, size=p.size)
            for p in existing_by_name.values()
            if p.category == "NATIVE" and p.name not in incoming_names and p.deleted_at is None
        ]
        for data in bulk.points:
            if data.category == "NATIVE":
                native_candidates.append(
                    NativePointRange(name=data.name, poll_kind=data.poll_kind, address=data.address, size=data.size)
                )
        # Ensures no two NATIVE points share registers within the same poll_kind.
        # A point occupies [address, address + size - 1] inclusive; overlap across
        # different poll_kinds (holding / input / coils) is allowed since they are
        # independent Modbus address spaces.
        validate_no_register_overlap(native_candidates)

        upserted: list[DevicePoint] = []
        for data in bulk.points:
            if data.name in existing_by_name:
                point = existing_by_name[data.name]
                point.deleted_at = None
                if data.poll_kind is not None:
                    point.poll_kind = data.poll_kind
                if data.address is not None:
                    point.address = data.address
                if data.size is not None:
                    point.size = data.size
                if data.data_type is not None:
                    point.data_type = data.data_type
                if data.scale_factor is not None:
                    point.scale_factor = data.scale_factor
                if data.unit is not None:
                    point.unit = data.unit
                if data.byte_order is not None:
                    point.byte_order = data.byte_order
                if data.word_order is not None:
                    point.word_order = data.word_order
                if data.bitfield_detail is not None:
                    point.bitfield_detail = data.bitfield_detail
                if data.enum_detail is not None:
                    point.enum_detail = data.enum_detail
                if data.point_class is not None:
                    point.point_class = data.point_class
                if data.severity is not None:
                    point.severity = data.severity
                upserted.append(point)
            else:
                new_point = DevicePoint(
                    site_id=site_id,
                    device_id=device_id,
                    name=data.name,
                    poll_kind=data.poll_kind,
                    address=data.address if data.address is not None else 0,
                    size=data.size,
                    data_type=data.data_type,
                    scale_factor=data.scale_factor,
                    unit=data.unit,
                    byte_order=data.byte_order,
                    word_order=data.word_order,
                    bitfield_detail=data.bitfield_detail,
                    enum_detail=data.enum_detail,
                    category=data.category,
                    point_class=data.point_class,
                    severity=data.severity,
                )
                session.add(new_point)
                upserted.append(new_point)

        await session.flush()
        await _recompute_scan_ranges(session, device_id)
        await session.commit()

        for pt in upserted:
            await session.refresh(pt)
        return upserted
