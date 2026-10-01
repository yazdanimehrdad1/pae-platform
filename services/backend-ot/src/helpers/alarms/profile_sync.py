"""Keep each site's PROFILE alarm rows in step with the alarms its profile declares in code.

Runs at app start (every site), and when a site is created or its profile changes. For each
declared SiteAlarm the site gets one alarm_definitions row (source PROFILE, found by key): created
if missing, its name/severity/message refreshed from code, restored if it was retired. A row whose
key the profile no longer declares is retired (soft-deleted); its history stays. A new (or restored)
row is enabled only while the site has room under MAX_ENABLED_ALARMS, else it stays disabled.
User settings on a row (enabled, notifications) are otherwise never touched.
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select

from db.connection import get_async_session_factory
from helpers.alarms.definitions import enabled_alarm_count
from logger import get_logger
from schemas.api_models.alarms import MAX_ENABLED_ALARMS
from schemas.db_models.orm_models import AlarmDefinition, Site
from site_profiles.profile_registry import SITE_PROFILES_BY_KEY
from site_profiles.site_alarm import SiteAlarm

logger = get_logger(__name__)


class ExistingProfileAlarm(BaseModel):
    """What the sync needs to know about a stored PROFILE row."""

    key: str
    name: str
    severity: str
    message: str
    deleted: bool


class ProfileAlarmSyncPlan(BaseModel):
    """What one site's sync will do, by profile alarm key."""

    create: list[str] = []
    refresh: list[str] = []
    retire: list[str] = []
    # Declared but not synced: the name is taken by one of the site's user alarms.
    name_taken: list[str] = []


def plan_profile_alarm_sync(
    existing: list[ExistingProfileAlarm], declared: tuple[SiteAlarm, ...], user_alarm_names: set[str]
) -> ProfileAlarmSyncPlan:
    """Pure: the changes that bring the stored rows in line with `declared`."""
    by_key = {row.key: row for row in existing}
    taken = {name.lower() for name in user_alarm_names}
    plan = ProfileAlarmSyncPlan()
    for alarm in declared:
        row = by_key.get(alarm.key)
        if alarm.name.lower() in taken and (row is None or row.deleted or row.name.lower() != alarm.name.lower()):
            plan.name_taken.append(alarm.key)
        elif row is None:
            plan.create.append(alarm.key)
        elif row.deleted or (row.name, row.severity, row.message) != (alarm.name, alarm.severity, alarm.message):
            plan.refresh.append(alarm.key)
    declared_keys = {alarm.key for alarm in declared}
    plan.retire = [row.key for row in existing if row.key not in declared_keys and not row.deleted]
    return plan


async def sync_site_profile_alarms(site_id: int) -> ProfileAlarmSyncPlan:
    """Apply the plan for one site, in one transaction."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        site = (await session.execute(select(Site).where(Site.id == site_id))).scalar_one_or_none()
        if site is None:
            return ProfileAlarmSyncPlan()
        profile = SITE_PROFILES_BY_KEY.get(site.profile)
        declared = profile.alarms if profile is not None else ()

        rows = (await session.execute(select(AlarmDefinition).where(AlarmDefinition.site_id == site_id))).scalars().all()
        profile_rows = {row.profile_alarm_key: row for row in rows if row.source == "PROFILE" and row.profile_alarm_key}
        user_names = {row.name for row in rows if row.source == "USER" and row.deleted_at is None}
        plan = plan_profile_alarm_sync(
            [
                ExistingProfileAlarm(key=key, name=row.name, severity=row.severity, message=row.message, deleted=row.deleted_at is not None)
                for key, row in profile_rows.items()
            ],
            declared,
            user_names,
        )

        declared_by_key = {alarm.key: alarm for alarm in declared}
        enabled_count = await enabled_alarm_count(session, site_id)

        def take_enabled_slot(key: str) -> bool:
            nonlocal enabled_count
            if enabled_count >= MAX_ENABLED_ALARMS:
                logger.warning(
                    "site %s: profile alarm '%s' left disabled, the site already has %s enabled alarms",
                    site_id, key, MAX_ENABLED_ALARMS,
                )
                return False
            enabled_count += 1
            return True

        for key in plan.create:
            alarm = declared_by_key[key]
            session.add(AlarmDefinition(
                site_id=site_id, source="PROFILE", profile_alarm_key=key, name=alarm.name, kind="profile",
                severity=alarm.severity, message=alarm.message, enabled=take_enabled_slot(key),
            ))
        for key in plan.refresh:
            alarm, row = declared_by_key[key], profile_rows[key]
            if row.deleted_at is not None and row.enabled:
                row.enabled = take_enabled_slot(key)  # a retired row wasn't counted; restored, it is
            row.name, row.severity, row.message, row.deleted_at = alarm.name, alarm.severity, alarm.message, None
        now = datetime.now(UTC)
        for key in plan.retire:
            profile_rows[key].deleted_at = now
        for key in plan.name_taken:
            logger.warning(
                "site %s: profile alarm '%s' not synced, its name '%s' is taken by a user alarm",
                site_id, key, declared_by_key[key].name,
            )
        await session.commit()
        return plan


async def sync_all_sites_profile_alarms() -> None:
    """At app start: sync every site. One site failing is logged and doesn't stop the others."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        site_ids = (await session.execute(select(Site.id).where(Site.deleted_at.is_(None)))).scalars().all()
    for site_id in site_ids:
        try:
            await sync_site_profile_alarms(site_id)
        except Exception as error:
            logger.error("site %s: profile alarm sync failed: %s", site_id, error, exc_info=True)
