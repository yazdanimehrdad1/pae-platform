"""Create, update, list and delete a site's alarm definitions.

USER alarms are fully editable, and deleting one removes it and its history permanently. PROFILE
alarms (from site_profiles code) accept only enabled and notifications, and can't be deleted. An
enabled alarm is evaluated and shown in Active alarms. Every write locks the site row first, so the
name check and the "at most MAX_ENABLED_ALARMS enabled per site" check can't race.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_async_session_factory
from helpers.device_points.point_inputs import check_input_points
from helpers.virtual_points.definition import bit_test_point_ids, condition_point_ids
from schemas.api_models.alarms import (
    MAX_ENABLED_ALARMS,
    PROFILE_EDITABLE_FIELDS,
    AlarmDefinitionCreateRequest,
    AlarmDefinitionResponse,
    AlarmDefinitionUpdateRequest,
    CommsStaleAlarm,
    ConditionAlarm,
    ThresholdAlarm,
    UserAlarmRule,
)
from schemas.db_models.orm_models import (
    AlarmDefinition,
    AlarmEvaluationState,
    AlarmEvent,
    Device,
    Site,
)
from utils.exceptions import ConflictError, NotFoundError, ValidationError


async def list_alarm_definitions(site_id: int, include_deleted: bool = False) -> list[AlarmDefinition]:
    """
    A site's alarms, user and profile, ordered by name (ignoring case).

    By default only live alarms; `include_deleted` adds retired profile alarms (their code was
    removed from the profile). Deleted user alarms are gone for good, so they never appear.
    Raises NotFoundError (404) if the site doesn't exist or is deleted.
    """
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        await _lock_site(session, site_id, lock=False)
        query = select(AlarmDefinition).where(AlarmDefinition.site_id == site_id).order_by(func.lower(AlarmDefinition.name))
        if not include_deleted:
            query = query.where(AlarmDefinition.deleted_at.is_(None))
        return list((await session.execute(query)).scalars().all())


def new_user_alarm(site_id: int, request: AlarmDefinitionCreateRequest) -> AlarmDefinition:
    """
    Build (don't save) the alarm_definitions row for a new USER alarm from its create request.

    Pure, with no checks and no database access: the caller validates first. The API's create
    path and the dev seeder both use it, so a seeded alarm is stored exactly like one created
    through the API.
    """
    return AlarmDefinition(
        site_id=site_id, source="USER", name=request.name, kind=request.rule.kind, rule=request.rule,
        severity=request.severity, message=request.message, enabled=request.enabled,
        notify_mobile=request.notify_mobile, notify_email=request.notify_email,
    )


async def create_user_alarm(site_id: int, request: AlarmDefinitionCreateRequest) -> AlarmDefinition:
    """
    Create a USER alarm on a site and return the stored row.

    Checks, in order, all under the site lock:
    - the site exists (NotFoundError, 404);
    - the name is free on the site, ignoring case, across user and profile alarms (ConflictError, 409);
    - the points or device the rule reads are active on this site, and bit tests read bitfields
      (ValidationError, 400);
    - if it starts enabled, the site has room under MAX_ENABLED_ALARMS (ConflictError, 409).
    """
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        await _lock_site(session, site_id)
        await _check_name_free(session, site_id, request.name)
        await _check_rule_inputs(session, site_id, request.rule)
        if request.enabled:
            await _check_enabled_room(session, site_id)
        alarm = new_user_alarm(site_id, request)
        session.add(alarm)
        await session.commit()
        await session.refresh(alarm)
        return alarm


async def update_alarm(site_id: int, alarm_id: int, request: AlarmDefinitionUpdateRequest) -> AlarmDefinition:
    """
    Change an alarm: only the fields the request sent; omitted fields keep their value.

    - A PROFILE alarm accepts only enabled, notify_mobile and notify_email; anything else is
      ValidationError (400), because the rest is defined in code. A null for a sent field is 400.
    - A new name must be free on the site (409).
    - A changed rule is checked like on create (400). It also clears the alarm's active event and
      deletes its evaluation state, so the new rule's delay starts from scratch. Sending the same
      rule again changes nothing.
    - Enabling needs room under MAX_ENABLED_ALARMS (409). Disabling clears the active event.
    - Name, severity, message and notifications leave an active event as it is.

    Raises NotFoundError (404) for an unknown site or alarm.
    """
    sent = request.model_fields_set
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        await _lock_site(session, site_id)
        alarm = await _get_alarm(session, site_id, alarm_id)
        if alarm.source == "PROFILE" and not sent <= PROFILE_EDITABLE_FIELDS:
            not_editable = sorted(sent - PROFILE_EDITABLE_FIELDS)
            raise ValidationError(
                f"Alarm {alarm_id} is defined in the site profile's code; only "
                f"{sorted(PROFILE_EDITABLE_FIELDS)} can change, not {not_editable}"
            )
        for field in sent:
            if getattr(request, field) is None:
                raise ValidationError(f"'{field}' can't be null")

        if request.name is not None and request.name.lower() != alarm.name.lower():
            await _check_name_free(session, site_id, request.name, alarm_id)
        if request.rule is not None and request.rule != alarm.rule:
            # What the alarm checks changed: an event raised by the old rule ends now, and the
            # new rule's delay starts from scratch (no evaluation state = a fresh start).
            await _check_rule_inputs(session, site_id, request.rule)
            alarm.rule, alarm.kind = request.rule, request.rule.kind
            await _clear_active_event(session, alarm.id)
            await session.execute(delete(AlarmEvaluationState).where(AlarmEvaluationState.definition_id == alarm.id))
        if request.enabled and not alarm.enabled:
            await _check_enabled_room(session, site_id)
        for field in sent - {"rule"}:
            setattr(alarm, field, getattr(request, field))
        if request.enabled is False:
            await _clear_active_event(session, alarm.id)

        await session.commit()
        await session.refresh(alarm)
        return alarm


async def delete_user_alarm(site_id: int, alarm_id: int) -> AlarmDefinitionResponse:
    """
    Permanently delete a USER alarm: its row, all its events (its history) and its evaluation
    state. The foreign keys cascade, so this is one delete.

    Returns the alarm as it was just before the delete. A PROFILE alarm can't be deleted
    (ValidationError, 400); disable it instead. Raises NotFoundError (404) for an unknown site or
    alarm.
    """
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        await _lock_site(session, site_id)
        alarm = await _get_alarm(session, site_id, alarm_id)
        if alarm.source == "PROFILE":
            raise ValidationError(
                f"Alarm {alarm_id} is defined in the site profile's code and can't be deleted; disable it instead"
            )
        deleted = AlarmDefinitionResponse.model_validate(alarm)
        await session.delete(alarm)
        await session.commit()
        return deleted


async def _lock_site(session: AsyncSession, site_id: int, *, lock: bool = True) -> None:
    """
    Check that the site exists and isn't deleted (else NotFoundError, 404), and lock its row
    (SELECT ... FOR UPDATE) until the transaction ends.

    Every write takes this lock first, so two concurrent writes on one site run one after the other.
    That keeps "the name is free" and "there is room under MAX_ENABLED_ALARMS" true until the
    commit. Reads pass `lock=False` to check existence only.
    """
    query = select(Site.id).where(Site.id == site_id, Site.deleted_at.is_(None))
    if lock:
        query = query.with_for_update()
    if (await session.execute(query)).first() is None:
        raise NotFoundError(f"Site {site_id} not found")


async def _get_alarm(session: AsyncSession, site_id: int, alarm_id: int) -> AlarmDefinition:
    """
    The site's live alarm with this id. NotFoundError (404) if there is none: the id is unknown,
    it belongs to another site, or it's a retired profile alarm.
    """
    alarm = (await session.execute(
        select(AlarmDefinition).where(
            AlarmDefinition.id == alarm_id, AlarmDefinition.site_id == site_id, AlarmDefinition.deleted_at.is_(None)
        )
    )).scalar_one_or_none()
    if alarm is None:
        raise NotFoundError(f"Alarm {alarm_id} not found on site {site_id}")
    return alarm


async def _check_name_free(session: AsyncSession, site_id: int, name: str, alarm_id: int | None = None) -> None:
    """
    ConflictError (409) if another live alarm on the site, user or profile, already has this
    name, ignoring case. On a rename, `alarm_id` is the renamed alarm, which doesn't count against
    itself. It mirrors the database's unique index on (site_id, lower(name)), but returns a clear
    message instead of an integrity error.
    """
    query = select(AlarmDefinition.id).where(
        AlarmDefinition.site_id == site_id,
        AlarmDefinition.deleted_at.is_(None),
        func.lower(AlarmDefinition.name) == name.lower(),
    )
    if alarm_id is not None:
        query = query.where(AlarmDefinition.id != alarm_id)
    if (await session.execute(query)).first() is not None:
        raise ConflictError(f"An alarm named '{name}' already exists on site {site_id} (names ignore case)")


async def enabled_alarm_count(session: AsyncSession, site_id: int) -> int:
    """
    How many of the site's live alarms (user and profile) are enabled, i.e. evaluated and shown in
    Active alarms. Used for the MAX_ENABLED_ALARMS limit here and by the profile alarm sync.
    """
    return (await session.execute(
        select(func.count()).select_from(AlarmDefinition).where(
            AlarmDefinition.site_id == site_id, AlarmDefinition.enabled.is_(True), AlarmDefinition.deleted_at.is_(None)
        )
    )).scalar_one()


async def _check_enabled_room(session: AsyncSession, site_id: int) -> None:
    """
    ConflictError (409) if the site already has MAX_ENABLED_ALARMS enabled alarms. Call it before
    creating an enabled alarm or enabling a disabled one. The error payload carries `max_enabled`
    for the UI.
    """
    if await enabled_alarm_count(session, site_id) >= MAX_ENABLED_ALARMS:
        raise ConflictError(
            f"Site {site_id} already has {MAX_ENABLED_ALARMS} enabled alarms; disable one first",
            payload={"max_enabled": MAX_ENABLED_ALARMS},
        )


async def _check_rule_inputs(session: AsyncSession, site_id: int, rule: UserAlarmRule) -> None:
    """
    Check that what a rule reads exists on this site, else ValidationError (400):
    - threshold or condition: every point it reads, including a compared-with point, is an active
      point of the site, and every point a bit test reads is a bitfield. Unlike a virtual point's
      inputs, an alarm may watch a virtual point. This reuses check_input_points, which the
      virtual-point save path also uses.
    - comms_stale: the device is an active device of the site.
    """
    match rule:
        case ThresholdAlarm():
            await check_input_points(
                session, site_id, condition_point_ids(rule.condition), bit_test_point_ids(rule.condition), allow_virtual=True
            )
        case ConditionAlarm():
            await check_input_points(
                session, site_id, condition_point_ids(rule.when), bit_test_point_ids(rule.when), allow_virtual=True
            )
        case CommsStaleAlarm():
            device = (await session.execute(
                select(Device).where(Device.device_id == rule.device_id)
            )).scalar_one_or_none()
            if device is None or device.site_id != site_id or device.deleted_at is not None:
                raise ValidationError(f"Device {rule.device_id} is not an active device of site {site_id}")


async def _clear_active_event(session: AsyncSession, definition_id: int) -> None:
    """
    End the alarm's active event, if it has one, by setting cleared_at to now. The event stays in
    the history as raised and cleared. Called when an alarm is disabled or its rule changes. A
    definition has at most one active event (a partial unique index), so this touches 0 or 1 rows.
    """
    await session.execute(
        update(AlarmEvent)
        .where(AlarmEvent.definition_id == definition_id, AlarmEvent.cleared_at.is_(None))
        .values(cleared_at=datetime.now(UTC))
    )
