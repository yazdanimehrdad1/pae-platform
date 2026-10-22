"""Link a STANDARDIZED point to a real point, and unlink it.

A STANDARDIZED point (BESS_ACTIVE_POWER, ...) is an empty placeholder until it is linked to an
active NATIVE point on the same device: source_point_id, plus the unit its values are in and the
scale_factor from the source's values (W -> kW: 0.001). Reads of a linked point return its
source's stored readings x scale_factor (helpers.reads.device_points_readings). The link is by id,
so renaming the device or either point keeps it; hard-deleting the source clears it (FK).
"""

import math

from sqlalchemy import select

from db.connection import get_async_session_factory
from schemas.api_models.requests import StandardizedPointLinkRequest
from schemas.db_models.orm_models import DevicePoint
from site_profiles.common.shared_helper_functions import POWER_UNIT_TO_KW
from utils.exceptions import NotFoundError, ValidationError


def power_scale_error(source_unit: str | None, unit: str | None, scale_factor: float) -> str | None:
    """Why scale_factor doesn't turn a power source's unit into `unit`, or None. Only power units
    (W, kW, MW) are checked; other quantities are taken as given."""
    if source_unit not in POWER_UNIT_TO_KW or unit not in POWER_UNIT_TO_KW:
        return None
    expected = POWER_UNIT_TO_KW[source_unit] / POWER_UNIT_TO_KW[unit]
    if math.isclose(scale_factor, expected):
        return None
    return f"scale_factor {scale_factor:g} doesn't turn {source_unit} into {unit} (expected {expected:g})"


def apply_point_link(point: DevicePoint, source: DevicePoint, request: StandardizedPointLinkRequest) -> None:
    """Check the link and set it on `point` (no DB). The dev seeder uses it too, so both stay identical."""
    if point.category != "STANDARDIZED":
        raise ValidationError(f"Point {point.id} is {point.category}; only STANDARDIZED points are linked")
    if source.device_id != point.device_id:
        raise ValidationError(f"Source point {source.id} is on device {source.device_id}, not on device {point.device_id}")
    if source.category != "NATIVE" or source.deleted_at is not None:
        raise ValidationError(f"Source point {source.id} must be an active NATIVE point")
    scale_error = power_scale_error(source.unit, request.unit, request.scale_factor)
    if scale_error is not None:
        raise ValidationError(scale_error)
    point.source_point_id = source.id
    point.unit = request.unit
    point.scale_factor = request.scale_factor


async def _get_point(session, site_id: int, device_id: int, point_id: int) -> DevicePoint:
    point = (await session.execute(
        select(DevicePoint).where(
            DevicePoint.id == point_id,
            DevicePoint.site_id == site_id,
            DevicePoint.device_id == device_id,
            DevicePoint.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if point is None:
        raise NotFoundError(f"Device point {point_id} not found on device {device_id}")
    return point


async def set_point_link(
    site_id: int, device_id: int, point_id: int, request: StandardizedPointLinkRequest
) -> DevicePoint:
    """Link the point (replacing any link it has)."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        point = await _get_point(session, site_id, device_id, point_id)
        source = await session.get(DevicePoint, request.source_point_id)
        if source is None:
            raise ValidationError(f"Source point {request.source_point_id} not found")
        apply_point_link(point, source, request)
        await session.commit()
        await session.refresh(point)
        return point


async def clear_point_link(site_id: int, device_id: int, point_id: int) -> DevicePoint:
    """Unlink the point: it is an empty placeholder again (no source, unit or scale)."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        point = await _get_point(session, site_id, device_id, point_id)
        if point.category != "STANDARDIZED":
            raise ValidationError(f"Point {point_id} is {point.category}; only STANDARDIZED points are linked")
        point.source_point_id, point.unit, point.scale_factor = None, None, None
        await session.commit()
        await session.refresh(point)
        return point
