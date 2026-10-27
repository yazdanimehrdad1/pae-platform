"""Keep each site's profile-owned VIRTUAL points in step with the virtual points its profile declares.

Runs at app start (every site), and when a site is created or its profile changes. Developers only
declare a SiteVirtualPoint; this creates its row. Every declared point is looked up before anything
is written, so running it again never makes a duplicate:
- the site has no device named `device_name` → skipped (logged);
- a point on that device already owns the key → refreshed (name, unit, description) and restored if deleted;
- a point on that device is called `point_name`: a VIRTUAL one is adopted (its formula is dropped,
  from now on the job stores its values), any other category is skipped (logged);
- otherwise a new VIRTUAL point is created.
A point whose key the profile no longer declares keeps its row and its stored history; the job
just stops computing it.
"""

from pydantic import BaseModel
from sqlalchemy import select

from db.connection import get_async_session_factory
from logger import get_logger
from schemas.api_models import register_size
from schemas.db_models.orm_models import Device, DevicePoint, Site
from site_profiles.declarations.virtual_point import SiteVirtualPoint
from site_profiles.profile_registry import SITE_PROFILES_BY_KEY

logger = get_logger(__name__)

PROFILE_POINT_DATA_TYPE = "float32"


class ExistingPoint(BaseModel):
    """What the sync needs to know about a stored point of the site (deleted ones included: the
    unique name and key constraints cover them too)."""

    id: int
    device_id: int
    name: str
    category: str
    profile_point_key: str | None


class ProfilePointSyncPlan(BaseModel):
    """What one site's sync will do, by declared key."""

    create: dict[str, int] = {}  # key -> device id
    adopt: dict[str, int] = {}  # key -> point id
    refresh: dict[str, int] = {}  # key -> point id
    missing_device: list[str] = []
    name_taken: list[str] = []


def plan_profile_point_sync(
    declared: tuple[SiteVirtualPoint, ...], device_ids_by_name: dict[str, int], existing: list[ExistingPoint]
) -> ProfilePointSyncPlan:
    """Pure: the changes that give every declared point its row."""
    plan = ProfilePointSyncPlan()
    for point in declared:
        device_id = device_ids_by_name.get(point.device_name)
        if device_id is None:
            plan.missing_device.append(point.key)
            continue
        on_device = [row for row in existing if row.device_id == device_id]
        owned = next((row for row in on_device if row.profile_point_key == point.key), None)
        if owned is not None:
            plan.refresh[point.key] = owned.id
            continue
        same_name = next((row for row in on_device if row.name == point.point_name), None)
        if same_name is None:
            plan.create[point.key] = device_id
        elif same_name.category == "VIRTUAL" and same_name.profile_point_key is None:
            plan.adopt[point.key] = same_name.id
        else:
            plan.name_taken.append(point.key)
    return plan


def _make_profile_owned(point: DevicePoint, declared: SiteVirtualPoint) -> None:
    """Shape a row as the declared point: stored float values, no formula, restored if deleted."""
    point.name = declared.point_name
    point.unit = declared.unit
    point.profile_point_description = declared.description
    point.category = "VIRTUAL"
    point.profile_point_key = declared.key
    point.virtual_definition = None
    point.data_type = PROFILE_POINT_DATA_TYPE
    point.size = register_size(PROFILE_POINT_DATA_TYPE)
    point.enum_detail = None
    point.bitfield_detail = None
    point.deleted_at = None


async def sync_site_profile_points(site_id: int) -> ProfilePointSyncPlan:
    """Apply the plan for one site, in one transaction."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        site = (await session.execute(select(Site).where(Site.id == site_id))).scalar_one_or_none()
        profile = SITE_PROFILES_BY_KEY.get(site.profile) if site is not None and site.profile is not None else None
        if profile is None or not profile.virtual_points:
            return ProfilePointSyncPlan()

        devices = (await session.execute(
            select(Device).where(Device.site_id == site_id, Device.deleted_at.is_(None))
        )).scalars().all()
        rows = {row.id: row for row in (await session.execute(
            select(DevicePoint).where(DevicePoint.site_id == site_id)
        )).scalars().all()}
        plan = plan_profile_point_sync(
            profile.virtual_points,
            {device.name: device.device_id for device in devices},
            [ExistingPoint.model_validate(row, from_attributes=True) for row in rows.values()],
        )

        declared_by_key = {point.key: point for point in profile.virtual_points}
        for key, point_id in {**plan.refresh, **plan.adopt}.items():
            _make_profile_owned(rows[point_id], declared_by_key[key])
        for key, device_id in plan.create.items():
            point = DevicePoint(site_id=site_id, device_id=device_id, address=0, poll_kind=None)
            _make_profile_owned(point, declared_by_key[key])
            session.add(point)
        for key in plan.adopt:
            logger.info("site %s: virtual point '%s' adopted by the profile", site_id, declared_by_key[key].point_name)
        for key in plan.missing_device:
            logger.warning(
                "site %s: profile virtual point '%s' not synced, the site has no device '%s'",
                site_id, key, declared_by_key[key].device_name,
            )
        for key in plan.name_taken:
            logger.warning(
                "site %s: profile virtual point '%s' not synced, '%s' is already a non-virtual point on device '%s'",
                site_id, key, declared_by_key[key].point_name, declared_by_key[key].device_name,
            )
        await session.commit()
        return plan


async def sync_all_sites_profile_points() -> None:
    """At app start: sync every site. One site failing is logged and doesn't stop the others."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        site_ids = (await session.execute(select(Site.id).where(Site.deleted_at.is_(None)))).scalars().all()
    for site_id in site_ids:
        try:
            await sync_site_profile_points(site_id)
        except Exception as error:
            logger.error("site %s: profile virtual point sync failed: %s", site_id, error, exc_info=True)
