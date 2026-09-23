"""
Device point readings database operations.

Handles CRUD operations for device_points_readings time-series table.
"""

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from typing_extensions import TypedDict

from db.session import get_session
from logger import get_logger
from schemas.api_models import DataType
from schemas.db_models.orm_models import DevicePointsReading

logger = get_logger(__name__)


class LatestDevicePointReadingDict(TypedDict):
    device_point_id: int
    register_address: int
    name: str
    data_type: DataType
    size: int
    unit: str | None
    scale_factor: float | None
    timestamp: datetime
    derived_value: float | None
    bitfield_detail: dict[str, str] | None
    enum_detail: dict[str, str] | None


class TimeSeriesDevicePointReadingDict(TypedDict):
    timestamp: datetime
    derived_value: float | None
    device_point_id: int
    register_address: int
    name: str
    data_type: DataType
    size: int
    unit: str | None
    scale_factor: float | None
    bitfield_detail: dict[str, str] | None
    enum_detail: dict[str, str] | None


async def insert_register_readings_batch(
    site_id: str | None,
    device_id: int,
    points_readings_list: list[DevicePointsReading],
    timestamp_dt: datetime
) -> int:
    """
    Insert multiple register readings in a single batch operation.

    Args:
        site_id: Optional Site ID (unused)
        readings: List of reading dictionaries, each containing:
            - device_id (int)
            - register_address (int)
            - value (float)
            - timestamp (datetime)
            - quality (str, optional, default 'good')
            - register_name (str, optional)
            - unit (str, optional)
            - scale_factor (float, optional)

    Returns:
        Number of successfully inserted readings

    Raises:
        ValueError: If site doesn't exist or any device doesn't belong to site
        Exception: For database errors
    """
    if not points_readings_list:
        logger.debug("No readings to insert in batch")
        return 0

    async with get_session() as session:
        values = []
        for r in points_readings_list:
            values.append({
                'site_id': r.site_id if r.site_id is not None else site_id,
                'device_id': r.device_id if r.device_id is not None else device_id,
                'device_point_id': r.device_point_id,
                'timestamp': r.timestamp,
                'derived_value': r.derived_value,
            })

        statement = insert(DevicePointsReading).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=['device_point_id', 'timestamp'],
            set_={"derived_value": statement.excluded.derived_value}
        )
        await session.execute(statement)
        await session.commit()

        inserted_count = len(values)
        logger.debug(f"Batch inserted {inserted_count} register readings")
        return inserted_count


async def insert_register_reading_single(
    site_id: str | None,
    device_id: int,
    reading: DevicePointsReading,
) -> bool:
    """
    Insert a single DevicePointsReading. Returns True on success, False on failure.
    Used as a per-row fallback when bulk insert fails.
    """
    try:
        async with get_session() as session:
            values = {
                'site_id': reading.site_id if reading.site_id is not None else site_id,
                'device_id': reading.device_id if reading.device_id is not None else device_id,
                'device_point_id': reading.device_point_id,
                'timestamp': reading.timestamp,
                'derived_value': reading.derived_value,
            }
            statement = insert(DevicePointsReading).values([values])
            statement = statement.on_conflict_do_update(
                index_elements=['device_point_id', 'timestamp'],
                set_={"derived_value": statement.excluded.derived_value}
            )
            await session.execute(statement)
            await session.commit()
            return True
    except Exception as e:
        logger.warning(f"Single insert failed for device_point_id={reading.device_point_id}: {e}")
        return False
