"""Reading alarm events: the page snapshot (now) and the history query (any range)."""

from datetime import datetime, timedelta

from sqlalchemy import func, or_, select

from db.connection import get_async_session_factory
from helpers.alarms.definitions import list_alarm_definitions
from schemas.api_models.alarms import (
    RECENT_WINDOW_HOURS,
    ActiveAlarmsSummaryResponse,
    AlarmDefinitionResponse,
    AlarmEventResponse,
    AlarmLogEntry,
    AlarmSeverity,
    AlarmSnapshotResponse,
    SiteActiveAlarms,
)
from schemas.db_models.orm_models import AlarmDefinition, AlarmEvent


def build_log(events: list[AlarmEventResponse], names: dict[int, str], since: datetime) -> list[AlarmLogEntry]:
    """Pure: a raise and (if any) a clear entry per event, only those at or after `since`, newest first.
    A raise logs the event's message; a clear logs '<alarm name> cleared'."""
    entries: list[AlarmLogEntry] = []
    for event in events:
        common = {"event_id": event.id, "definition_id": event.definition_id, "device_id": event.device_id, "severity": event.severity}
        if event.raised_at >= since:
            entries.append(AlarmLogEntry(id=f"{event.id}:raised", kind="raised", at=event.raised_at, message=event.message, **common))
        if event.cleared_at is not None and event.cleared_at >= since:
            name = names.get(event.definition_id, f"alarm {event.definition_id}")
            entries.append(AlarmLogEntry(id=f"{event.id}:cleared", kind="cleared", at=event.cleared_at, message=f"{name} cleared", **common))
    return sorted(entries, key=lambda entry: entry.at, reverse=True)


async def get_alarm_snapshot(site_id: int, now: datetime) -> AlarmSnapshotResponse:
    """The site's alarms, its active events and those cleared recently, and the recent log."""
    definitions = [AlarmDefinitionResponse.model_validate(alarm) for alarm in await list_alarm_definitions(site_id)]
    since = now - timedelta(hours=RECENT_WINDOW_HOURS)
    events = await query_alarm_events(site_id, start_time=since, end_time=now)
    names = {definition.id: definition.name for definition in definitions}
    return AlarmSnapshotResponse(
        site_id=site_id, now=now, definitions=definitions, events=events, log=build_log(events, names, since),
    )


async def query_alarm_events(
    site_id: int,
    start_time: datetime,
    end_time: datetime,
    device_id: int | None = None,
    severity: AlarmSeverity | None = None,
    definition_id: int | None = None,
) -> list[AlarmEventResponse]:
    """Events that overlap [start_time, end_time] (an active one runs until now), newest raise first.
    Events of deleted alarms are gone with them; events of retired profile alarms stay."""
    query = (
        select(AlarmEvent)
        .join(AlarmDefinition, AlarmDefinition.id == AlarmEvent.definition_id)
        .where(
            AlarmEvent.site_id == site_id,
            AlarmEvent.raised_at <= end_time,
            or_(AlarmEvent.cleared_at.is_(None), AlarmEvent.cleared_at >= start_time),
        )
        .order_by(AlarmEvent.raised_at.desc(), AlarmEvent.id.desc())
    )
    if device_id is not None:
        query = query.where(AlarmEvent.device_id == device_id)
    if severity is not None:
        query = query.where(AlarmEvent.severity == severity)
    if definition_id is not None:
        query = query.where(AlarmEvent.definition_id == definition_id)
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        return [AlarmEventResponse.model_validate(event) for event in (await session.execute(query)).scalars().all()]


def build_active_summary(counts: list[tuple[int, AlarmSeverity, int]]) -> ActiveAlarmsSummaryResponse:
    """Pure: (site_id, severity, active count) rows → totals plus one entry per site, by site_id."""
    per_site: dict[int, SiteActiveAlarms] = {}
    for site_id, severity, count in counts:
        site = per_site.setdefault(site_id, SiteActiveAlarms(site_id=site_id, fault_count=0, warning_count=0))
        if severity == "fault":
            site.fault_count += count
        else:
            site.warning_count += count
    sites = [per_site[site_id] for site_id in sorted(per_site)]
    return ActiveAlarmsSummaryResponse(
        fault_count=sum(site.fault_count for site in sites),
        warning_count=sum(site.warning_count for site in sites),
        sites=sites,
    )


async def get_active_alarm_summary() -> ActiveAlarmsSummaryResponse:
    """Active events (raised, not cleared) of every site, counted by site and severity."""
    query = (
        select(AlarmEvent.site_id, AlarmEvent.severity, func.count())
        .where(AlarmEvent.cleared_at.is_(None))
        .group_by(AlarmEvent.site_id, AlarmEvent.severity)
    )
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        rows = (await session.execute(query)).all()
    return build_active_summary([(site_id, severity, count) for site_id, severity, count in rows])


async def count_active_device_events(device_id: int, severity: AlarmSeverity) -> int:
    """How many alarms of this severity are active (raised, not cleared) for the device."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(AlarmEvent).where(
                AlarmEvent.device_id == device_id,
                AlarmEvent.severity == severity,
                AlarmEvent.cleared_at.is_(None),
            )
        )
        return count or 0
