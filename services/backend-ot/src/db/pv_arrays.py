"""
PV array config database operations (the pv_array_configs table).

At most one config per device. The callers check that the device exists, belongs to the site
and is a PV or INVERTER device; this module only reads and writes rows.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from db.connection import get_async_session_factory
from logger import get_logger
from schemas.api_models import PvArrayConfigResponse, PvArrayConfigUpsertRequest
from schemas.db_models.orm_models import Device, PvArrayConfigRecord
from utils.exceptions import InternalError

logger = get_logger(__name__)


def _to_response(record: PvArrayConfigRecord, device: Device) -> PvArrayConfigResponse:
    return PvArrayConfigResponse(
        device_id=record.device_id,
        site_id=device.site_id,
        device_name=device.name,
        device_type=device.type,
        tilt_deg=record.tilt_deg,
        azimuth_deg=record.azimuth_deg,
        dc_capacity_kw=record.dc_capacity_kw,
        ac_capacity_kw=record.ac_capacity_kw,
        system_loss_pct=record.system_loss_pct,
        temp_coefficient_pct_per_c=record.temp_coefficient_pct_per_c,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def get_site_pv_arrays(site_id: int) -> list[PvArrayConfigResponse]:
    """The array configs of the site's active (not soft-deleted) devices, by device id."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        rows = await session.execute(
            select(PvArrayConfigRecord, Device)
            .join(Device, Device.device_id == PvArrayConfigRecord.device_id)
            .where(Device.site_id == site_id, Device.deleted_at.is_(None))
            .order_by(PvArrayConfigRecord.device_id)
        )
        return [_to_response(record, device) for record, device in rows.tuples()]


async def get_device_pv_array(device_id: int) -> PvArrayConfigResponse | None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        row = (
            await session.execute(
                select(PvArrayConfigRecord, Device)
                .join(Device, Device.device_id == PvArrayConfigRecord.device_id)
                .where(PvArrayConfigRecord.device_id == device_id)
            )
        ).first()
        if row is None:
            return None
        record, device = row
        return _to_response(record, device)


async def upsert_device_pv_array(
    device_id: int, config: PvArrayConfigUpsertRequest
) -> PvArrayConfigResponse:
    """Create the device's array config, or replace every field of the existing one."""
    values = config.model_dump()
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        statement = (
            insert(PvArrayConfigRecord)
            .values(device_id=device_id, **values)
            .on_conflict_do_update(
                index_elements=[PvArrayConfigRecord.device_id],
                set_={**values, "updated_at": func.now()},
            )
            .returning(PvArrayConfigRecord)
        )
        record = await session.scalar(statement)
        device = await session.get(Device, device_id)
        await session.commit()
        if record is None or device is None:  # the caller checked the device exists
            raise InternalError(f"Device {device_id} vanished while saving its PV array config")
        logger.info(f"Saved PV array config for device {device_id}")
        return _to_response(record, device)


async def delete_device_pv_array(device_id: int) -> PvArrayConfigResponse | None:
    """Delete the device's array config and return it; None if it had none."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        device = await session.get(Device, device_id)
        deleted = await session.scalar(
            delete(PvArrayConfigRecord)
            .where(PvArrayConfigRecord.device_id == device_id)
            .returning(PvArrayConfigRecord)
        )
        if deleted is None or device is None:
            return None
        await session.commit()
        logger.info(f"Deleted PV array config for device {device_id}")
        return _to_response(deleted, device)
