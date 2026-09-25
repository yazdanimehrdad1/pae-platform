"""Seed the database with development mock data.

Idempotent — safe to run multiple times. Skips rows that already exist.

Run via:
    make seed-db                    # copies files into running container then executes
    python tests/seed_db/seed_db.py # run locally (requires DB to be reachable)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from db.session import get_session  # noqa: E402
from helpers.device_points.device_standardized_points import (  # noqa: E402
    generate_standardized_points,
)
from helpers.device_points.scan_range_computation import (  # noqa: E402
    compute_device_scan_ranges,
)
from logger import get_logger  # noqa: E402
from schemas.api_models.responses import DevicePointResponse  # noqa: E402
from schemas.db_models.orm_models import Device, DevicePoint, Site  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dev_mock_data import DEVICE_POINTS, DEVICES, SITES  # noqa: E402

logger = get_logger(__name__)


async def seed() -> None:
    async with get_session() as session:

        # ------------------------------------------------------------------ #
        # 1. Sites                                                            #
        # ------------------------------------------------------------------ #
        site_by_name: dict[str, Site] = {}
        for site_request in SITES:
            result = await session.execute(
                select(Site).where(Site.name == site_request.name)
            )
            site = result.scalar_one_or_none()
            if site is None:
                site = Site(**site_request.model_dump())
                session.add(site)
                await session.flush()
                logger.info("Created site '%s' (id=%s)", site.name, site.id)
            else:
                logger.info("Site already exists '%s' (id=%s)", site.name, site.id)
            site_by_name[site.name] = site

        # ------------------------------------------------------------------ #
        # 2. Devices                                                          #
        # ------------------------------------------------------------------ #
        device_by_name: dict[str, Device] = {}
        for seed_device in DEVICES:
            site = site_by_name[seed_device.site_name]

            result = await session.execute(
                select(Device).where(Device.name == seed_device.device.name)
            )
            device = result.scalar_one_or_none()
            if device is None:
                device = Device(**seed_device.device.model_dump(), site_id=site.id)
                session.add(device)
                await session.flush()
                logger.info("Created device '%s' (id=%s)", device.name, device.device_id)
            else:
                logger.info(
                    "Device already exists '%s' (id=%s)", device.name, device.device_id
                )
            device_by_name[device.name] = device

        # ------------------------------------------------------------------ #
        # 3. Device points, device by device, in the order the API creates    #
        #    them, so ids follow the same pattern as API-created devices:     #
        #    STANDARDIZED (POST /api/devices/site/{id}/devices creates them   #
        #    with the device, via the same helper), then NATIVE (added       #
        #    afterwards), then VIRTUAL (none in the seed data yet). A flush   #
        #    after each category makes the database assign ids in that order. #
        # ------------------------------------------------------------------ #
        async def point_exists(device: Device, name: str) -> bool:
            result = await session.execute(
                select(DevicePoint).where(
                    DevicePoint.site_id == device.site_id,
                    DevicePoint.device_id == device.device_id,
                    DevicePoint.name == name,
                )
            )
            return result.scalar_one_or_none() is not None

        for device_name, device in device_by_name.items():
            # STANDARDIZED
            for point in generate_standardized_points(device.type, device.device_id, device.site_id):
                if await point_exists(device, point.name):
                    logger.info("Device point already exists '%s.%s'", device_name, point.name)
                    continue
                session.add(DevicePoint(**point.model_dump()))
                logger.info("Created standardized point '%s.%s'", device_name, point.name)
            await session.flush()

            # NATIVE
            for point in DEVICE_POINTS.get(device_name, []):
                if await point_exists(device, point.name):
                    logger.info("Device point already exists '%s.%s'", device_name, point.name)
                    continue
                session.add(DevicePoint(
                    site_id=device.site_id,
                    device_id=device.device_id,
                    address=point.address,
                    name=point.name,
                    size=point.size,
                    data_type=point.data_type,
                    scale_factor=point.scale_factor if point.scale_factor is not None else 1.0,
                    unit=point.unit,
                    poll_kind=point.poll_kind,
                    category=point.category,
                    byte_order=point.byte_order,
                    word_order=point.word_order,
                    bitfield_detail=point.bitfield_detail,
                    enum_detail=point.enum_detail,
                ))
                logger.info(
                    "Created device point '%s.%s' (addr=%s)",
                    device_name, point.name, point.address,
                )
            await session.flush()

            # VIRTUAL: the seed data defines none. Add them here, after NATIVE, if it ever does.

        # ------------------------------------------------------------------ #
        # 4. Recompute scan_ranges from each device's active NATIVE points    #
        # ------------------------------------------------------------------ #
        for device in device_by_name.values():
            if device.scan_ranges_locked:
                logger.info(
                    "Scan ranges locked for '%s' — leaving untouched", device.name
                )
                continue

            points_result = await session.execute(
                select(DevicePoint).where(
                    DevicePoint.device_id == device.device_id,
                    DevicePoint.category == "NATIVE",
                    DevicePoint.deleted_at.is_(None),
                )
            )
            native_points = [
                DevicePointResponse.model_validate(point)
                for point in points_result.scalars().all()
            ]
            device.scan_ranges = compute_device_scan_ranges(native_points).model_dump()
            logger.info("Computed scan ranges for '%s': %s", device.name, device.scan_ranges)

        # ------------------------------------------------------------------ #
        # 5. Sync device_count on each site                                   #
        # ------------------------------------------------------------------ #
        for site in site_by_name.values():
            count_result = await session.execute(
                select(func.count()).select_from(Device).where(Device.site_id == site.id)
            )
            site.device_count = count_result.scalar_one()

        await session.commit()
        logger.info("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
