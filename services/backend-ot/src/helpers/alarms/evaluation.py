"""Evaluate a site's alarms once: read what they watch, run the engine, record raises and clears.

Called by the scheduler job `alarm_evaluation` every poll interval, for every site. Inputs come
from the database only:
- threshold / condition: the latest stored reading of each point (virtual points computed on read),
  ignored when older than `input_max_gap()`;
- comms-stale: the device's last successful poll, i.e. its newest stored NATIVE reading;
- profile: the alarm's own check, with an AlarmContext of the site.

A raise inserts an alarm_events row (and logs the notification channels that would fire; sending
them is not built yet); a clear sets its cleared_at. Every enabled alarm is evaluated (and shown
in Active alarms); a disabled one clears its active event. One alarm failing is logged and skips only that alarm.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import db.devices as devices_db
import db.sites as sites_db
from db.connection import get_async_session_factory
from helpers.alarms.engine import (
    AlarmObservation,
    AlarmState,
    AlarmTransition,
    disabled_step,
    observe_comms_stale,
    observe_condition,
    observe_threshold,
    step,
)
from helpers.reads.device_points_readings import get_latest_readings_by_point_ids
from helpers.virtual_points.definition import condition_point_ids
from helpers.virtual_points.resolve import input_max_gap
from logger import get_logger
from schemas.api_models.alarms import CommsStaleAlarm, ConditionAlarm, ThresholdAlarm
from schemas.db_models.orm_models import (
    AlarmDefinition,
    AlarmEvaluationState,
    AlarmEvent,
    DevicePoint,
    DevicePointsReading,
)
from schemas.site_profiles import AlarmContext
from site_profiles.declarations.profile import SiteProfile
from site_profiles.profile_registry import SITE_PROFILES_BY_KEY

logger = get_logger(__name__)


async def evaluate_site_alarms(site_id: int, now: datetime) -> list[AlarmTransition]:
    """One evaluation cycle for a site. Returns the raises and clears it recorded."""
    site = await sites_db.get_site_by_id(site_id)
    if site is None:
        return []
    devices = await devices_db.get_all_devices(site_id)
    context = AlarmContext(site=site, devices=devices, now=now)
    profile = SITE_PROFILES_BY_KEY.get(site.profile)

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        alarms = list((await session.execute(
            select(AlarmDefinition).where(AlarmDefinition.site_id == site_id, AlarmDefinition.deleted_at.is_(None))
        )).scalars().all())
        if not alarms:
            return []
        alarm_ids = [alarm.id for alarm in alarms]
        active_events = {event.definition_id: event for event in (await session.execute(
            select(AlarmEvent).where(AlarmEvent.definition_id.in_(alarm_ids), AlarmEvent.cleared_at.is_(None))
        )).scalars().all()}
        stored_states = {state.definition_id: state for state in (await session.execute(
            select(AlarmEvaluationState).where(AlarmEvaluationState.definition_id.in_(alarm_ids))
        )).scalars().all()}

        enabled = [alarm for alarm in alarms if alarm.enabled]
        values, device_of = await _point_values(site_id, enabled, now)
        last_success = await _last_successful_polls(session, enabled)

        transitions: list[AlarmTransition] = []
        for alarm in alarms:
            stored = stored_states.get(alarm.id)
            state = AlarmState(active=alarm.id in active_events, condition_since=stored.condition_since if stored else None)
            try:
                if not alarm.enabled:
                    new_state, transition = disabled_step(state, now)
                else:
                    observation, delay = await _observe(alarm, context, profile, values, device_of, last_success, now)
                    new_state, transition = step(state, observation, delay, now)
            except Exception as error:
                logger.error("site %s: alarm %s ('%s') evaluation failed: %s", site_id, alarm.id, alarm.name, error, exc_info=True)
                continue

            if transition is not None:
                _record(session, alarm, transition, active_events.get(alarm.id))
                transitions.append(transition)
            if stored is None:
                session.add(AlarmEvaluationState(definition_id=alarm.id, condition_since=new_state.condition_since, last_evaluated_at=now))
            else:
                stored.condition_since, stored.last_evaluated_at = new_state.condition_since, now

        await session.commit()
        return transitions


async def _observe(
    alarm: AlarmDefinition,
    context: AlarmContext,
    profile: SiteProfile | None,
    values: Mapping[int, float | None],
    device_of: Mapping[int, int],
    last_success: Mapping[int, datetime],
    now: datetime,
) -> tuple[AlarmObservation | None, timedelta]:
    """The observation for one alarm, and the delay before it may raise."""
    if alarm.source == "PROFILE":
        declared = profile.find_alarm(alarm.profile_alarm_key) if profile else None
        if declared is None:
            return None, timedelta(0)
        check = await declared.evaluate(context)
        return AlarmObservation(holds=check.active, cleared=not check.active, value=check.value, device_id=check.device_id), timedelta(0)
    rule = alarm.rule
    match rule:
        case ThresholdAlarm():
            return observe_threshold(rule, values, device_of), timedelta(seconds=rule.delay_sec)
        case ConditionAlarm():
            return observe_condition(rule, values, device_of), timedelta(seconds=rule.delay_sec)
        case CommsStaleAlarm():
            return observe_comms_stale(rule, last_success.get(rule.device_id), now), timedelta(0)
        case _:
            return None, timedelta(0)  # a stored rule that no longer parses


def _record(session: AsyncSession, alarm: AlarmDefinition, transition: AlarmTransition, active: AlarmEvent | None) -> None:
    if transition.kind == "raise":
        session.add(AlarmEvent(
            definition_id=alarm.id, site_id=alarm.site_id, device_id=transition.device_id, severity=alarm.severity,
            raised_at=transition.at, value_at_raise=transition.value, message=alarm.message or alarm.name,
        ))
        channels = [channel for channel, on in (("mobile", alarm.notify_mobile), ("email", alarm.notify_email)) if on]
        logger.info(
            "alarm raised: site %s, %s ('%s'), %s; would notify: %s",
            alarm.site_id, alarm.id, alarm.name, alarm.severity, ", ".join(channels) or "none",
        )
    elif active is not None:
        active.cleared_at = max(transition.at, active.raised_at)
        logger.info("alarm cleared: site %s, %s ('%s')", alarm.site_id, alarm.id, alarm.name)


async def _point_values(site_id: int, alarms: list[AlarmDefinition], now: datetime) -> tuple[dict[int, float | None], dict[int, int]]:
    """Latest value of every point the alarms read (None when missing or older than the max gap),
    and each point's device."""
    point_ids: set[int] = set()
    for alarm in alarms:
        match alarm.rule:
            case ThresholdAlarm():
                point_ids |= condition_point_ids(alarm.rule.condition)
            case ConditionAlarm():
                point_ids |= condition_point_ids(alarm.rule.when)
    if not point_ids:
        return {}, {}
    oldest = now - input_max_gap()
    readings = await get_latest_readings_by_point_ids(sorted(point_ids), site_id=site_id)
    values = {
        reading.device_point_id: reading.derived_value if reading.timestamp is not None and reading.timestamp >= oldest else None
        for reading in readings
    }
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        device_of = dict((await session.execute(
            select(DevicePoint.id, DevicePoint.device_id).where(DevicePoint.id.in_(point_ids))
        )).tuples().all())
    return values, device_of


async def _last_successful_polls(session: AsyncSession, alarms: list[AlarmDefinition]) -> dict[int, datetime]:
    """Per watched device: when its newest NATIVE reading with a value was stored."""
    device_ids = {alarm.rule.device_id for alarm in alarms if isinstance(alarm.rule, CommsStaleAlarm)}
    if not device_ids:
        return {}
    rows = await session.execute(
        select(DevicePointsReading.device_id, func.max(DevicePointsReading.timestamp))
        .join(DevicePoint, DevicePoint.id == DevicePointsReading.device_point_id)
        .where(
            DevicePointsReading.device_id.in_(device_ids),
            DevicePoint.category == "NATIVE",
            DevicePointsReading.derived_value.is_not(None),
        )
        .group_by(DevicePointsReading.device_id)
    )
    return dict(rows.tuples().all())


async def evaluate_all_sites_alarms(now: datetime) -> None:
    """The job body: every site, one at a time. A site failing is logged and doesn't stop the others."""
    for site in await sites_db.get_all_sites():
        try:
            await evaluate_site_alarms(site.site_id, now)
        except Exception as error:
            logger.error("site %s: alarm evaluation failed: %s", site.site_id, error, exc_info=True)
