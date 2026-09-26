"""
Site database operations.

Handles CRUD operations for sites table.
Uses SQLAlchemy 2.0+ async ORM.
"""

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.connection import get_async_session_factory
from logger import get_logger
from schemas.api_models import SiteCreateRequest, SiteResponse, SiteUpdateRequest
from schemas.db_models.orm_models import Device, DevicePoint, Site
from utils.exceptions import (
    AppError,
    ConflictError,
    InternalError,
    NotFoundError,
    ValidationError,
)

logger = get_logger(__name__)


def _site_to_response(site: Site) -> SiteResponse:
    coordinates = None
    if site.coordinates:
        from schemas.api_models import Coordinates
        coordinates = Coordinates(lat=site.coordinates["lat"], lng=site.coordinates["lng"])
    location = None
    if site.location:
        from schemas.api_models import Location
        location = Location(**site.location)
    return SiteResponse(
        site_id=site.id,
        client_id=site.client_id,
        name=site.name,
        location=location,
        operator=site.operator,
        capacity=site.capacity,
        device_count=site.device_count,
        description=site.description,
        coordinates=coordinates,
        profile=site.profile,
        created_at=site.created_at,
        updated_at=site.updated_at,
        last_update=site.last_update,
        deleted_at=site.deleted_at,
    )


async def create_site(site: SiteCreateRequest) -> SiteResponse:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            # Check active site with same name
            existing_site = await session.execute(
                select(Site).where(Site.name == site.name, Site.deleted_at.is_(None))
            )
            if existing_site.scalar_one_or_none() is not None:
                raise ConflictError(f"Site with name '{site.name}' already exists")

            # Check soft-deleted site with same name — suggest restore
            soft_deleted = await session.execute(
                select(Site).where(Site.name == site.name, Site.deleted_at.is_not(None))
            )
            sd = soft_deleted.scalar_one_or_none()
            if sd is not None:
                raise ConflictError(
                    f"A soft-deleted site named '{site.name}' exists (site_id={sd.id}). "
                    f"Use POST /sites/{sd.id}/restore to restore it."
                )

            location_dict = site.location.model_dump()
            coordinates_dict = None
            if site.coordinates:
                coordinates_dict = {"lat": site.coordinates.lat, "lng": site.coordinates.lng}

            new_site = Site(
                client_id=site.client_id,
                name=site.name,
                location=location_dict,
                operator=site.operator,
                capacity=site.capacity,
                description=site.description,
                coordinates=coordinates_dict,
                profile=site.profile,
                device_count=0,
            )

            session.add(new_site)
            await session.flush()
            logger.info(f"Created site: {site.name} (ID: {new_site.id})")
            await session.commit()

            return _site_to_response(new_site)

        except IntegrityError as error:
            await session.rollback()
            error_msg = str(error)
            logger.error(f"Database integrity error creating site '{site.name}': {error_msg}", exc_info=True)
            raise ValidationError(f"Database constraint violation: {error_msg}") from error
        except Exception as error:
            await session.rollback()
            logger.error(f"Database error creating site '{site.name}': {type(error).__name__}: {error}", exc_info=True)
            raise


async def get_all_sites(include_deleted: bool = False) -> list[SiteResponse]:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        query = select(Site).order_by(Site.created_at.desc())
        if not include_deleted:
            query = query.where(Site.deleted_at.is_(None))
        result = await session.execute(query)
        return [_site_to_response(site) for site in result.scalars().all()]


async def get_site_by_id(site_id: int, include_deleted: bool = False) -> SiteResponse | None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        query = select(Site).where(Site.id == site_id)
        if not include_deleted:
            query = query.where(Site.deleted_at.is_(None))
        result = await session.execute(query)
        site = result.scalar_one_or_none()
        if site is None:
            return None
        return _site_to_response(site)


async def update_site(site_id: int, site_update: SiteUpdateRequest) -> SiteResponse:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            result = await session.execute(
                select(Site).where(Site.id == site_id, Site.deleted_at.is_(None))
            )
            site = result.scalar_one_or_none()

            if site is None:
                raise NotFoundError(f"Site with id {site_id} not found")

            if site_update.client_id is not None:
                site.client_id = site_update.client_id
            if site_update.name is not None:
                site.name = site_update.name
            if site_update.location is not None:
                site.location = site_update.location.model_dump()
            if site_update.operator is not None:
                site.operator = site_update.operator
            if site_update.capacity is not None:
                site.capacity = site_update.capacity
            if site_update.description is not None:
                site.description = site_update.description
            if site_update.coordinates is not None:
                site.coordinates = {"lat": site_update.coordinates.lat, "lng": site_update.coordinates.lng}
            if site_update.profile is not None:
                site.profile = site_update.profile

            site.last_update = datetime.now(UTC)

            await session.commit()
            await session.refresh(site)
            logger.info(f"Updated site with id {site_id}")

            return _site_to_response(site)

        except IntegrityError as e:
            await session.rollback()
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                logger.warning("Site name already exists")
                raise ConflictError("Site with this name already exists") from e
            else:
                logger.error(f"Database integrity error updating site: {e}")
                raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error updating site: {e}")
            raise


async def delete_site(
    site_id: int,
    mode: Literal["soft", "hard"] = "soft",
    confirm: bool = False,
) -> SiteResponse | None:
    if mode == "hard" and not confirm:
        raise ValidationError("Set confirm=true to permanently delete a site and all its data")

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            result = await session.execute(select(Site).where(Site.id == site_id))
            site = result.scalar_one_or_none()

            if site is None:
                logger.warning(f"Site with id {site_id} not found for deletion")
                return None

            site_response = _site_to_response(site)

            if mode == "soft":
                now = datetime.now(UTC)
                site.deleted_at = now
                site_response.deleted_at = now

                # Cascade soft-delete to all active devices and their points
                devices_result = await session.execute(
                    select(Device).where(
                        Device.site_id == site_id,
                        Device.deleted_at.is_(None),
                    )
                )
                for device in devices_result.scalars().all():
                    device.deleted_at = now
                    points_result = await session.execute(
                        select(DevicePoint).where(
                            DevicePoint.device_id == device.device_id,
                            DevicePoint.deleted_at.is_(None),
                        )
                    )
                    for pt in points_result.scalars().all():
                        pt.deleted_at = now

                await session.commit()
                logger.info(f"Soft-deleted site {site_id} and all its devices/points")

            else:
                # Hard delete: block if any active (non-soft-deleted) devices remain
                device_result = await session.execute(
                    select(Device.device_id).where(
                        Device.site_id == site_id,
                        Device.deleted_at.is_(None),
                    )
                )
                active_device_ids = [row[0] for row in device_result.all()]
                if active_device_ids:
                    joined_ids = ", ".join(str(did) for did in active_device_ids)
                    raise ConflictError(
                        f"Site {site_id} has active devices: {joined_ids}. "
                        f"Soft-delete or delete them first.",
                        payload={"device_ids": active_device_ids},
                    )

                await session.delete(site)
                await session.flush()
                await session.commit()
                logger.info(f"Hard-deleted site '{site.name}' (id={site_id})")

            return site_response

        except Exception as e:
            await session.rollback()
            logger.error(f"Database error deleting site: {e}")
            raise


async def restore_site(site_id: int) -> SiteResponse | None:
    """Restore a soft-deleted site, all its soft-deleted devices, and their soft-deleted points."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            result = await session.execute(select(Site).where(Site.id == site_id))
            site = result.scalar_one_or_none()

            if site is None:
                return None
            if site.deleted_at is None:
                raise ConflictError(f"Site {site_id} is not soft-deleted")

            site.deleted_at = None

            devices_result = await session.execute(
                select(Device).where(
                    Device.site_id == site_id,
                    Device.deleted_at.is_not(None),
                )
            )
            for device in devices_result.scalars().all():
                device.deleted_at = None
                points_result = await session.execute(
                    select(DevicePoint).where(
                        DevicePoint.device_id == device.device_id,
                        DevicePoint.deleted_at.is_not(None),
                    )
                )
                for pt in points_result.scalars().all():
                    pt.deleted_at = None

            await session.commit()
            logger.info(f"Restored site {site_id} and all its devices/points")

        except AppError:
            # Our own NotFound/Conflict errors carry the right status; don't wrap them as 500.
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error restoring site: {e}")
            raise InternalError(f"Failed to restore site: {e}") from e

    return await get_site_by_id(site_id)
