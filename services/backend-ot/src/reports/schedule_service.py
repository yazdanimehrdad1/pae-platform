"""What /api/reports/site/{site_id}/schedules does: a site's report schedules. A schedule's next time
is worked out here (in the site's time zone) whenever it is created, changed or re-enabled."""

from datetime import UTC, datetime

from helpers.common.date_time import resolve_timezone
from reports import repository, schedule_repository
from reports.cadence import next_run_time
from reports.data_source import ReportDataSource
from reports.windows import resolve_window, window_length_error
from schemas.reports.api import ReportScheduleResponse
from schemas.reports.internal import ReportSiteContext, ScheduleFields
from schemas.reports.schedules import (
    ReportCadence,
    ReportScheduleCreateRequest,
    ReportScheduleUpdateRequest,
)
from utils.exceptions import NotFoundError, ValidationError


async def _site(site_id: int, data_source: ReportDataSource) -> ReportSiteContext:
    site = await data_source.get_site_context(site_id)
    if site is None:
        raise NotFoundError(f"Site {site_id} not found")
    return site


def _next_run_at(cadence: ReportCadence, enabled: bool, site: ReportSiteContext, now: datetime) -> datetime | None:
    return next_run_time(cadence, resolve_timezone(site.site.timezone), now) if enabled else None


async def _check(site: ReportSiteContext, fields: ScheduleFields, now: datetime) -> None:
    """The template must be the site's, and an overriding custom range at most 92 days."""
    try:
        await repository.get_template(site.site.site_id, fields.template_id)
    except NotFoundError as error:
        raise ValidationError(f"Report template {fields.template_id} is not on this site") from error
    if fields.window_override is not None:
        start, end = resolve_window(fields.window_override, now, resolve_timezone(site.site.timezone))
        error = window_length_error(start, end)
        if error:
            raise ValidationError(error)


async def list_schedules(site_id: int, data_source: ReportDataSource) -> list[ReportScheduleResponse]:
    site = await _site(site_id, data_source)
    return await schedule_repository.list_schedules(site_id, site.site.timezone)


async def get_schedule(site_id: int, schedule_id: int, data_source: ReportDataSource) -> ReportScheduleResponse:
    site = await _site(site_id, data_source)
    return await schedule_repository.get_schedule(site_id, schedule_id, site.site.timezone)


async def create_schedule(
    site_id: int, request: ReportScheduleCreateRequest, data_source: ReportDataSource, now: datetime | None = None
) -> ReportScheduleResponse:
    now = now or datetime.now(UTC)
    site = await _site(site_id, data_source)
    fields = ScheduleFields(
        **request.model_dump(exclude={"cadence", "window_override"}),
        cadence=request.cadence,
        window_override=request.window_override,
        next_run_at=_next_run_at(request.cadence, request.enabled, site, now),
    )
    await _check(site, fields, now)
    schedule_id = await schedule_repository.create_schedule(site_id, fields)
    return await schedule_repository.get_schedule(site_id, schedule_id, site.site.timezone)


async def update_schedule(
    site_id: int, schedule_id: int, request: ReportScheduleUpdateRequest, data_source: ReportDataSource,
    now: datetime | None = None,
) -> ReportScheduleResponse:
    """Omitted fields keep their value. The next time is worked out again from now (re-enabling a
    schedule doesn't generate the occurrences it missed while off)."""
    now = now or datetime.now(UTC)
    site = await _site(site_id, data_source)
    current = await schedule_repository.get_schedule(site_id, schedule_id, site.site.timezone)
    changes = request.model_dump(exclude_unset=True, exclude={"cadence", "window_override"})
    cadence = request.cadence if "cadence" in request.model_fields_set and request.cadence is not None else current.cadence
    window_override = request.window_override if "window_override" in request.model_fields_set else current.window_override
    enabled = changes.get("enabled", current.enabled)
    fields = ScheduleFields(
        template_id=current.template_id,
        cadence=cadence,
        window_override=window_override,
        enabled=enabled,
        keep_last=changes.get("keep_last", current.keep_last),
        keep_days=changes.get("keep_days", current.keep_days),
        next_run_at=_next_run_at(cadence, enabled, site, now),
    )
    await _check(site, fields, now)
    await schedule_repository.update_schedule(site_id, schedule_id, fields)
    return await schedule_repository.get_schedule(site_id, schedule_id, site.site.timezone)


async def delete_schedule(site_id: int, schedule_id: int, data_source: ReportDataSource) -> ReportScheduleResponse:
    """Returns the schedule as it was. Its reports stay."""
    site = await _site(site_id, data_source)
    deleted = await schedule_repository.get_schedule(site_id, schedule_id, site.site.timezone)
    await schedule_repository.delete_schedule(site_id, schedule_id)
    return deleted
