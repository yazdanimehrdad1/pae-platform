"""
The reports module's own tables: report_templates and report_runs.

report_runs is also the work queue: a run is inserted 'queued', claimed by the worker with
FOR UPDATE SKIP LOCKED (so two workers never take the same run), and finished as 'succeeded'
(with its result) or 'failed' (with an error).
"""

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy import func as sql_func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import defer

from db.connection import get_async_session_factory
from schemas.db_models.orm_models import ReportRun, ReportTemplate
from schemas.reports import ReportDefinition, ReportSnapshot
from schemas.reports.api import (
    ReportRunResponse,
    ReportRunStatus,
    ReportRunSummary,
    ReportRunTrigger,
    ReportTemplateCreateRequest,
    ReportTemplateResponse,
    ReportTemplateUpdateRequest,
)
from utils.exceptions import ConflictError, InternalError, NotFoundError

_TEMPLATE_NAME_INDEX = "uq_report_templates_site_name"


def _template_response(template: ReportTemplate) -> ReportTemplateResponse:
    if template.definition is None:
        raise InternalError(f"The stored definition of report template {template.id} is invalid")
    return ReportTemplateResponse.model_validate(template)


def _name_conflict(error: IntegrityError, name: str) -> ConflictError | None:
    if _TEMPLATE_NAME_INDEX in str(error):
        return ConflictError(f"A report template named '{name}' already exists on this site")
    return None


# --- Templates ---------------------------------------------------------------------------


async def list_templates(site_id: int) -> list[ReportTemplateResponse]:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(ReportTemplate).where(ReportTemplate.site_id == site_id).order_by(ReportTemplate.name)
        )
        return [_template_response(template) for template in result.scalars().all()]


async def get_template(site_id: int, template_id: int) -> ReportTemplateResponse:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        template = await session.scalar(
            select(ReportTemplate).where(ReportTemplate.site_id == site_id, ReportTemplate.id == template_id)
        )
        if template is None:
            raise NotFoundError(f"Report template {template_id} not found on site {site_id}")
        return _template_response(template)


async def create_template(site_id: int, request: ReportTemplateCreateRequest) -> ReportTemplateResponse:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        template = ReportTemplate(
            site_id=site_id, name=request.name, description=request.description, definition=request.definition
        )
        session.add(template)
        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            conflict = _name_conflict(error, request.name)
            if conflict is not None:
                raise conflict from error
            raise
        await session.refresh(template)
        return _template_response(template)


async def update_template(
    site_id: int, template_id: int, request: ReportTemplateUpdateRequest
) -> ReportTemplateResponse:
    """Omitted fields keep their value; a definition that differs from the stored one bumps the version."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        template = await session.scalar(
            select(ReportTemplate).where(ReportTemplate.site_id == site_id, ReportTemplate.id == template_id)
        )
        if template is None:
            raise NotFoundError(f"Report template {template_id} not found on site {site_id}")
        if request.name is not None:
            template.name = request.name
        if request.description is not None:
            template.description = request.description
        if request.definition is not None and _changed(template.definition, request.definition):
            template.definition = request.definition
            template.version += 1
        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            conflict = _name_conflict(error, request.name or template.name)
            if conflict is not None:
                raise conflict from error
            raise
        await session.refresh(template)
        return _template_response(template)


def _changed(stored: ReportDefinition | None, new: ReportDefinition) -> bool:
    return stored is None or stored.model_dump(mode="json") != new.model_dump(mode="json")


async def delete_template(site_id: int, template_id: int) -> ReportTemplateResponse:
    """Delete the template; its runs stay (their template_id becomes null)."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        template = await session.scalar(
            select(ReportTemplate).where(ReportTemplate.site_id == site_id, ReportTemplate.id == template_id)
        )
        if template is None:
            raise NotFoundError(f"Report template {template_id} not found on site {site_id}")
        deleted = _template_response(template)
        await session.delete(template)
        await session.commit()
        return deleted


# --- Runs --------------------------------------------------------------------------------


def _run_response(run: ReportRun) -> ReportRunResponse:
    if run.definition is None:
        raise InternalError(f"The stored definition of report run {run.id} is invalid")
    return ReportRunResponse.model_validate(run)


async def insert_run(
    site_id: int,
    name: str,
    definition: ReportDefinition,
    window_start: datetime,
    window_end: datetime,
    trigger: ReportRunTrigger,
    template_id: int | None = None,
    template_version: int | None = None,
    schedule_id: int | None = None,
    failed_error: str | None = None,
) -> ReportRunResponse:
    """A queued run; or, with `failed_error`, one that failed before it could be generated (a
    scheduled template that no longer fits its site), listed so the failure is seen."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        run = ReportRun(
            site_id=site_id, template_id=template_id, template_version=template_version, schedule_id=schedule_id,
            name=name, definition=definition, window_start=window_start, window_end=window_end,
            status="failed" if failed_error else "queued", trigger=trigger, error=failed_error,
            finished_at=sql_func.now() if failed_error else None,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return _run_response(run)


async def list_runs(
    site_id: int, template_id: int | None = None, status: ReportRunStatus | None = None, limit: int = 50,
    schedule_id: int | None = None,
) -> list[ReportRunSummary]:
    """Newest request first, without the definitions and results (they can be large)."""
    query = (
        select(ReportRun)
        .options(defer(ReportRun.definition), defer(ReportRun.result))
        .where(ReportRun.site_id == site_id)
        .order_by(ReportRun.requested_at.desc(), ReportRun.id.desc())
        .limit(limit)
    )
    if template_id is not None:
        query = query.where(ReportRun.template_id == template_id)
    if schedule_id is not None:
        query = query.where(ReportRun.schedule_id == schedule_id)
    if status is not None:
        query = query.where(ReportRun.status == status)
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        return [ReportRunSummary.model_validate(run) for run in (await session.execute(query)).scalars().all()]


async def get_run(site_id: int, run_id: int) -> ReportRunResponse:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        run = await session.scalar(select(ReportRun).where(ReportRun.site_id == site_id, ReportRun.id == run_id))
        if run is None:
            raise NotFoundError(f"Report run {run_id} not found on site {site_id}")
        return _run_response(run)


async def get_run_by_id(run_id: int) -> ReportRunResponse | None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        run = await session.get(ReportRun, run_id)
        return _run_response(run) if run is not None else None


async def delete_run(site_id: int, run_id: int) -> ReportRunSummary:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        run = await session.scalar(
            select(ReportRun)
            .options(defer(ReportRun.definition), defer(ReportRun.result))
            .where(ReportRun.site_id == site_id, ReportRun.id == run_id)
        )
        if run is None:
            raise NotFoundError(f"Report run {run_id} not found on site {site_id}")
        deleted = ReportRunSummary.model_validate(run)
        await session.execute(delete(ReportRun).where(ReportRun.id == run_id))
        await session.commit()
        return deleted


async def delete_runs(site_id: int) -> int:
    """Delete every report of the site (queued and generating ones too); returns how many. A run
    the worker is generating at that moment finishes into nothing."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(delete(ReportRun).where(ReportRun.site_id == site_id).returning(ReportRun.id))
        await session.commit()
        return len(result.all())


async def claim_next_queued_run(now: datetime) -> int | None:
    """Mark the oldest queued run 'running' and return its id; None if the queue is empty. SKIP
    LOCKED lets several workers claim at once without taking the same run."""
    oldest_queued = (
        select(ReportRun.id)
        .where(ReportRun.status == "queued")
        .order_by(ReportRun.requested_at, ReportRun.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        run_id = await session.scalar(
            update(ReportRun)
            .where(ReportRun.id == oldest_queued)
            .values(status="running", started_at=now)
            .returning(ReportRun.id)
        )
        await session.commit()
        return run_id


async def finish_run(run_id: int, now: datetime, result: ReportSnapshot | None = None, error: str | None = None) -> None:
    """'succeeded' with the result, or 'failed' with the error."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        await session.execute(
            update(ReportRun)
            .where(ReportRun.id == run_id)
            .values(
                status="succeeded" if result is not None else "failed",
                result=result,
                error=None if result is not None else (error or "Report generation failed"),
                finished_at=now,
            )
        )
        await session.commit()


async def fail_stale_runs(started_before: datetime, now: datetime) -> int:
    """Fail runs still 'running' that started before `started_before` (their worker stopped, e.g.
    the app restarted mid-run). Returns how many."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            update(ReportRun)
            .where(ReportRun.status == "running", ReportRun.started_at < started_before)
            .values(status="failed", error="Interrupted: the report stopped generating. Request it again.", finished_at=now)
            .returning(ReportRun.id)
        )
        await session.commit()
        return len(result.all())
