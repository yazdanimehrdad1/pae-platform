"""
The report_schedules table, and the retention it applies to its own reports.

A due schedule is claimed by moving it to its next time with a conditional UPDATE (only if it is
still due at the time read), so two workers never generate the same occurrence.
"""

from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy import func as sql_func

from db.connection import get_async_session_factory
from schemas.db_models.orm_models import ReportRun, ReportSchedule, ReportTemplate
from schemas.reports.api import ReportScheduleResponse
from schemas.reports.internal import DueSchedule, ScheduleFields
from utils.exceptions import InternalError, NotFoundError


def _response(schedule: ReportSchedule, template_name: str, timezone: str) -> ReportScheduleResponse:
    if schedule.cadence is None:
        raise InternalError(f"The stored cadence of report schedule {schedule.id} is invalid")
    return ReportScheduleResponse(
        id=schedule.id, site_id=schedule.site_id, template_id=schedule.template_id, template_name=template_name,
        cadence=schedule.cadence, window_override=schedule.window_override, enabled=schedule.enabled,
        keep_last=schedule.keep_last, keep_days=schedule.keep_days, next_run_at=schedule.next_run_at,
        last_run_at=schedule.last_run_at, timezone=timezone, created_at=schedule.created_at, updated_at=schedule.updated_at,
    )


def _with_template_name():
    return select(ReportSchedule, ReportTemplate.name).join(ReportTemplate, ReportTemplate.id == ReportSchedule.template_id)


async def list_schedules(site_id: int, timezone: str) -> list[ReportScheduleResponse]:
    """The site's schedules, by template name, then oldest first."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        rows = (await session.execute(
            _with_template_name().where(ReportSchedule.site_id == site_id).order_by(ReportTemplate.name, ReportSchedule.id)
        )).all()
        return [_response(schedule, name, timezone) for schedule, name in rows]


async def get_schedule(site_id: int, schedule_id: int, timezone: str) -> ReportScheduleResponse:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        row = (await session.execute(
            _with_template_name().where(ReportSchedule.site_id == site_id, ReportSchedule.id == schedule_id)
        )).first()
        if row is None:
            raise NotFoundError(f"Report schedule {schedule_id} not found on site {site_id}")
        return _response(row[0], row[1], timezone)


async def create_schedule(site_id: int, fields: ScheduleFields) -> int:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        schedule = ReportSchedule(site_id=site_id, **fields.model_dump())
        session.add(schedule)
        await session.commit()
        return schedule.id


async def update_schedule(site_id: int, schedule_id: int, fields: ScheduleFields) -> None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        schedule = await session.scalar(
            select(ReportSchedule).where(ReportSchedule.site_id == site_id, ReportSchedule.id == schedule_id)
        )
        if schedule is None:
            raise NotFoundError(f"Report schedule {schedule_id} not found on site {site_id}")
        for name, value in fields.model_dump().items():
            setattr(schedule, name, value)
        await session.commit()


async def delete_schedule(site_id: int, schedule_id: int) -> None:
    """Delete the schedule; the reports it generated stay (their schedule_id becomes null)."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            delete(ReportSchedule)
            .where(ReportSchedule.site_id == site_id, ReportSchedule.id == schedule_id)
            .returning(ReportSchedule.id)
        )
        if result.first() is None:
            raise NotFoundError(f"Report schedule {schedule_id} not found on site {site_id}")
        await session.commit()


async def list_due_schedules(now: datetime) -> list[DueSchedule]:
    """Enabled schedules whose next time is at or before `now`, the longest due first."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        rows = (await session.execute(
            select(ReportSchedule, ReportTemplate)
            .join(ReportTemplate, ReportTemplate.id == ReportSchedule.template_id)
            .where(ReportSchedule.enabled.is_(True), ReportSchedule.next_run_at <= now)
            .order_by(ReportSchedule.next_run_at, ReportSchedule.id)
        )).all()
    due: list[DueSchedule] = []
    for schedule, template in rows:
        if schedule.cadence is None or template.definition is None or schedule.next_run_at is None:
            continue  # a stored value that no longer parses; logged by the column type
        definition = template.definition
        if schedule.window_override is not None:
            definition = definition.model_copy(update={"window": schedule.window_override})
        due.append(DueSchedule(
            schedule_id=schedule.id, site_id=schedule.site_id, template_id=template.id, template_name=template.name,
            template_version=template.version, definition=definition, cadence=schedule.cadence,
            keep_last=schedule.keep_last, keep_days=schedule.keep_days, due_at=schedule.next_run_at,
        ))
    return due


async def advance_schedule(schedule_id: int, due_at: datetime, next_run_at: datetime | None) -> bool:
    """Move a due schedule to its next time, only if it is still due at `due_at`. Returns whether
    this caller claimed the occurrence."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            update(ReportSchedule)
            .where(ReportSchedule.id == schedule_id, ReportSchedule.next_run_at == due_at, ReportSchedule.enabled.is_(True))
            .values(next_run_at=next_run_at, last_run_at=sql_func.now())
            .returning(ReportSchedule.id)
        )
        await session.commit()
        return result.first() is not None


async def prune_schedule_runs(schedule_id: int, keep_last: int | None, keep_days: int | None, now: datetime) -> int:
    """Apply a schedule's retention to its own reports (never to reports requested by hand): keep
    the newest `keep_last`, and none requested more than `keep_days` ago. Returns how many it deleted."""
    if keep_last is None and keep_days is None:
        return 0
    conditions = []
    if keep_last is not None:
        newest = (
            select(ReportRun.id)
            .where(ReportRun.schedule_id == schedule_id)
            .order_by(ReportRun.requested_at.desc(), ReportRun.id.desc())
            .limit(keep_last)
        )
        conditions.append(ReportRun.id.not_in(newest))
    if keep_days is not None:
        conditions.append(ReportRun.requested_at < now - timedelta(days=keep_days))
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            delete(ReportRun).where(ReportRun.schedule_id == schedule_id, or_(*conditions)).returning(ReportRun.id)
        )
        await session.commit()
        return len(result.all())
