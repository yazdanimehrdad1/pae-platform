"""
Site single line diagram database operations (the site_slds table).

One diagram per site. Saves use optimistic locking: an update names the revision it replaces,
and the UPDATE only matches while that revision is current, so two editors can't silently
overwrite each other. The callers check that the site exists first.
"""

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from db.connection import get_async_session_factory
from logger import get_logger
from schemas.api_models import SiteSld, SiteSldResponse
from schemas.db_models.orm_models import SiteSldRecord
from utils.exceptions import ConflictError, InternalError

logger = get_logger(__name__)


def _to_response(record: SiteSldRecord) -> SiteSldResponse:
    if record.document is None:
        # Only if a stored document stopped parsing (e.g. edited by hand in SQL).
        raise InternalError(f"The stored single line diagram of site {record.site_id} is invalid")
    return SiteSldResponse(
        site_id=record.site_id,
        revision=record.revision,
        created_at=record.created_at,
        updated_at=record.updated_at,
        sld=record.document,
    )


async def get_site_sld(site_id: int) -> SiteSldResponse | None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        record = await session.scalar(select(SiteSldRecord).where(SiteSldRecord.site_id == site_id))
        return _to_response(record) if record is not None else None


async def create_site_sld(site_id: int, sld: SiteSld) -> SiteSldResponse:
    """The site's first diagram (revision 1). 409 if it already has one."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        statement = (
            insert(SiteSldRecord)
            .values(site_id=site_id, document=sld)
            .on_conflict_do_nothing(index_elements=[SiteSldRecord.site_id])
            .returning(SiteSldRecord)
        )
        record = await session.scalar(statement)
        if record is None:
            raise ConflictError(
                f"Site {site_id} already has a single line diagram; send its revision to replace it"
            )
        await session.commit()
        logger.info(f"Created single line diagram for site {site_id}")
        return _to_response(record)


async def update_site_sld(site_id: int, sld: SiteSld, revision: int) -> SiteSldResponse:
    """Replace the diagram if `revision` is still current; the revision then increments. 409 otherwise."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        statement = (
            update(SiteSldRecord)
            .where(SiteSldRecord.site_id == site_id, SiteSldRecord.revision == revision)
            .values(document=sld, revision=SiteSldRecord.revision + 1, updated_at=func.now())
            .returning(SiteSldRecord)
        )
        record = await session.scalar(statement)
        if record is None:
            current = await session.scalar(
                select(SiteSldRecord.revision).where(SiteSldRecord.site_id == site_id)
            )
            if current is None:
                raise ConflictError(
                    f"Site {site_id} has no single line diagram to replace; omit revision to create it"
                )
            raise ConflictError(
                f"Single line diagram of site {site_id} is at revision {current}, not {revision}; "
                f"reload it and apply your changes again",
                payload={"current_revision": current},
            )
        await session.commit()
        logger.info(f"Updated single line diagram for site {site_id} to revision {record.revision}")
        return _to_response(record)


async def delete_site_sld(site_id: int) -> SiteSldResponse | None:
    """Delete the site's diagram and return it; None if it had none."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        deleted = await session.scalar(
            delete(SiteSldRecord).where(SiteSldRecord.site_id == site_id).returning(SiteSldRecord)
        )
        if deleted is None:
            return None
        await session.commit()
        logger.info(f"Deleted single line diagram for site {site_id}")
        return _to_response(deleted)
