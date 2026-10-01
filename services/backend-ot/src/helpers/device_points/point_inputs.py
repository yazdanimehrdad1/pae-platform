"""Checks on the points a computed thing reads (a virtual point's inputs, an alarm rule's points).

Shared by the virtual point and alarm save paths, so both reject the same bad references with the
same 400 messages.
"""

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.db_models.orm_models import DevicePoint
from utils.exceptions import ValidationError

BIT_CAPABLE_TYPE_PREFIXES = ("bitfield", "status_word")


async def check_input_points(
    session: AsyncSession,
    site_id: int,
    point_ids: Collection[int],
    bit_test_point_ids: Collection[int] = (),
    *,
    allow_virtual: bool,
) -> None:
    """Every point exists on `site_id` and is active; bit tests read bitfields; VIRTUAL points only
    when `allow_virtual` (a virtual point can't read another virtual point; an alarm can)."""
    wanted = set(point_ids)
    result = await session.execute(select(DevicePoint).where(DevicePoint.id.in_(wanted)))
    points_by_id = {point.id: point for point in result.scalars().all()}

    missing = sorted(wanted - points_by_id.keys())
    if missing:
        raise ValidationError(f"Input points not found: {missing}")
    for point in points_by_id.values():
        if point.site_id != site_id:
            raise ValidationError(f"Input point {point.id} ('{point.name}') is on another site")
        if point.deleted_at is not None:
            raise ValidationError(f"Input point {point.id} ('{point.name}') is deleted")
        if point.category == "VIRTUAL" and not allow_virtual:
            raise ValidationError(
                f"Input point {point.id} ('{point.name}') is virtual; virtual points can't read other virtual points"
            )
    for point_id in bit_test_point_ids:
        point = points_by_id[point_id]
        if not point.data_type.startswith(BIT_CAPABLE_TYPE_PREFIXES):
            raise ValidationError(f"Bit conditions need a bitfield point; '{point.name}' is {point.data_type}")
