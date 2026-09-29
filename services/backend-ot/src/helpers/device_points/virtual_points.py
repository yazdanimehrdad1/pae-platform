"""Create and update VIRTUAL points.

A virtual point reads other points on its site (any device). Its storage columns are derived from
the definition: a condition is an enum16 whose enum_detail holds the case labels, a calculation is
a float32. It has no register (address 0, no poll_kind), so it is never decoded from Modbus.
"""

from typing import assert_never

from sqlalchemy import select

from db.connection import get_async_session_factory
from helpers.virtual_points.definition import (
    bit_condition_point_ids,
    condition_enum_detail,
    referenced_point_ids,
)
from schemas.api_models import DataType, register_size
from schemas.api_models.requests import VirtualPointCreateRequest, VirtualPointUpdateRequest
from schemas.api_models.virtual_points import (
    VirtualCalculationDefinition,
    VirtualConditionDefinition,
    VirtualDefinition,
)
from schemas.db_models.orm_models import DevicePoint
from utils.exceptions import ConflictError, NotFoundError, ValidationError

BIT_CAPABLE_TYPE_PREFIXES = ("bitfield", "status_word")


def virtual_point_storage(definition: VirtualDefinition) -> tuple[DataType, dict[str, str] | None]:
    """(data_type, enum_detail) a virtual point is stored with, from its definition's kind."""
    match definition:
        case VirtualConditionDefinition():
            return "enum16", condition_enum_detail(definition)
        case VirtualCalculationDefinition():
            return "float32", None
        case _:
            assert_never(definition)


async def _check_name_free(session, site_id: int, device_id: int, name: str, point_id: int | None = None) -> None:
    query = select(DevicePoint.id).where(
        DevicePoint.site_id == site_id, DevicePoint.device_id == device_id, DevicePoint.name == name
    )
    if point_id is not None:
        query = query.where(DevicePoint.id != point_id)
    if (await session.execute(query)).first() is not None:
        raise ConflictError(f"A point named '{name}' already exists on device {device_id}")


async def _check_inputs(
    session, site_id: int, definition: VirtualDefinition
) -> None:
    """Every input must be an active, non-virtual point on the same site; bit tests need a bitfield."""
    input_ids = referenced_point_ids(definition)
    result = await session.execute(select(DevicePoint).where(DevicePoint.id.in_(input_ids)))
    inputs_by_id = {point.id: point for point in result.scalars().all()}

    missing = sorted(input_ids - inputs_by_id.keys())
    if missing:
        raise ValidationError(f"Input points not found: {missing}")
    for point in inputs_by_id.values():
        if point.site_id != site_id:
            raise ValidationError(f"Input point {point.id} ('{point.name}') is on another site")
        if point.deleted_at is not None:
            raise ValidationError(f"Input point {point.id} ('{point.name}') is deleted")
        if point.category == "VIRTUAL":
            raise ValidationError(
                f"Input point {point.id} ('{point.name}') is virtual; virtual points can't read other virtual points"
            )
    for point_id in bit_condition_point_ids(definition):
        point = inputs_by_id[point_id]
        if not point.data_type.startswith(BIT_CAPABLE_TYPE_PREFIXES):
            raise ValidationError(
                f"Bit conditions need a bitfield point; '{point.name}' is {point.data_type}"
            )


def _apply_definition(
    point: DevicePoint, definition: VirtualDefinition
) -> None:
    data_type, enum_detail = virtual_point_storage(definition)
    point.data_type = data_type
    point.size = register_size(data_type)
    point.enum_detail = enum_detail
    point.virtual_definition = definition


def new_virtual_point(site_id: int, device_id: int, request: VirtualPointCreateRequest) -> DevicePoint:
    """The row a create stores (no checks). The dev seeder uses it too, so both stay identical."""
    point = DevicePoint(
        site_id=site_id,
        device_id=device_id,
        name=request.name,
        address=0,
        poll_kind=None,
        unit=request.unit,
        category="VIRTUAL",
        point_class=request.point_class,
        severity=request.severity,
    )
    _apply_definition(point, request.definition)
    return point


async def create_virtual_point(site_id: int, device_id: int, request: VirtualPointCreateRequest) -> DevicePoint:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        await _check_name_free(session, site_id, device_id, request.name)
        await _check_inputs(session, site_id, request.definition)
        point = new_virtual_point(site_id, device_id, request)
        session.add(point)
        await session.commit()
        await session.refresh(point)
        return point


async def update_virtual_point(
    site_id: int, device_id: int, point_id: int, request: VirtualPointUpdateRequest
) -> DevicePoint:
    """Update fields that were sent; unit, class and severity can be cleared by sending null."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(DevicePoint).where(DevicePoint.id == point_id, DevicePoint.device_id == device_id)
        )
        point = result.scalar_one_or_none()
        if point is None:
            raise NotFoundError(f"Device point {point_id} not found on device {device_id}")
        if point.category != "VIRTUAL":
            raise ValidationError(f"Point {point_id} is {point.category}, not VIRTUAL; update it with PUT .../{point_id}")

        sent = request.model_fields_set
        if request.name is not None:
            await _check_name_free(session, site_id, device_id, request.name, point_id)
            point.name = request.name
        if request.definition is not None:
            await _check_inputs(session, site_id, request.definition)
            _apply_definition(point, request.definition)
        if "unit" in sent:
            point.unit = request.unit
        if "point_class" in sent:
            point.point_class = request.point_class
        if "severity" in sent:
            point.severity = request.severity

        await session.commit()
        await session.refresh(point)
        return point

