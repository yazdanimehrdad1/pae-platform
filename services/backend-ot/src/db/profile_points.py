"""Stored values and job state of profile-owned VIRTUAL points (helpers.profile_points)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db.session import get_session
from schemas.db_models.orm_models import DevicePoint, DevicePointsReading, ProfilePointState
from schemas.internal_models import TimestampedValue


async def get_profile_points(site_id: int) -> list[DevicePoint]:
    """The site's active profile-owned points."""
    async with get_session() as session:
        result = await session.execute(
            select(DevicePoint).where(
                DevicePoint.site_id == site_id,
                DevicePoint.profile_point_key.is_not(None),
                DevicePoint.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())


async def get_computed_until(point_ids: list[int]) -> dict[int, datetime]:
    """How far each point has been computed; a point never computed is missing."""
    if not point_ids:
        return {}
    async with get_session() as session:
        result = await session.execute(
            select(ProfilePointState).where(ProfilePointState.device_point_id.in_(point_ids))
        )
        return {state.device_point_id: state.computed_until for state in result.scalars().all()}


async def store_computed_values(point: DevicePoint, values: list[TimestampedValue], computed_until: datetime) -> None:
    """Upsert the point's values into device_points_readings and move its watermark, in one
    transaction: either both land or neither does, so a failed write is recomputed."""
    async with get_session() as session:
        if values:
            readings = insert(DevicePointsReading).values([
                {
                    "site_id": point.site_id,
                    "device_id": point.device_id,
                    "device_point_id": point.id,
                    "timestamp": value.time,
                    "derived_value": value.value,
                }
                for value in values
            ])
            await session.execute(readings.on_conflict_do_update(
                index_elements=["device_point_id", "timestamp"],
                set_={"derived_value": readings.excluded.derived_value},
            ))
        state = insert(ProfilePointState).values(device_point_id=point.id, computed_until=computed_until)
        await session.execute(state.on_conflict_do_update(
            index_elements=["device_point_id"], set_={"computed_until": state.excluded.computed_until}
        ))
        await session.commit()
