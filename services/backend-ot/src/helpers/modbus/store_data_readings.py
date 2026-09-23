"""Helpers for storing device polling data."""

from dataclasses import dataclass
from datetime import datetime

from db.register_readings import insert_register_reading_single, insert_register_readings_batch
from logger import get_logger
from schemas.db_models.orm_models import DevicePointsReading

logger = get_logger(__name__)


@dataclass
class DbStoreResult:
    successful: int
    failed: int
    used_fallback: bool = False


async def store_device_data_in_db(
    device_id: int,
    site_id: str,
    points_readings_list: list[DevicePointsReading],
    timestamp_dt: datetime,
    device_name: str = "",
) -> DbStoreResult:
    """
    Store device point readings in the database.

    Tries a single bulk INSERT first. If that fails, falls back to inserting
    one row at a time so good rows still make it through.
    """
    if not points_readings_list:
        return DbStoreResult(successful=0, failed=0)

    try:
        inserted_count = await insert_register_readings_batch(
            site_id=site_id,
            device_id=device_id,
            points_readings_list=points_readings_list,
            timestamp_dt=timestamp_dt,
        )
        logger.info(f"site_id='{site_id}', device_name='{device_name}': bulk insert stored {inserted_count} readings")
        return DbStoreResult(successful=inserted_count, failed=0)

    except Exception as e:
        logger.warning(
            f"site_id='{site_id}', device_name='{device_name}': bulk insert failed ({e}), "
            f"falling back to one-by-one inserts for {len(points_readings_list)} readings",
            exc_info=True,
        )

    successful = 0
    failed = 0
    for reading in points_readings_list:
        ok = await insert_register_reading_single(
            site_id=site_id,
            device_id=device_id,
            reading=reading,
        )
        if ok:
            successful += 1
        else:
            failed += 1

    logger.info(f"site_id='{site_id}', device_name='{device_name}': one-by-one fallback — {successful} stored, {failed} failed")
    return DbStoreResult(successful=successful, failed=failed, used_fallback=True)
