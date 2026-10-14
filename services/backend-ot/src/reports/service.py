"""
What /api/reports does: templates, requesting and reading runs, and the builder's catalog.

Every template and every requested run is checked against its site first (reports.validation),
and a run's window is resolved when it is requested, so a stored report always covers the window
it was asked for, however long it waits in the queue.
"""

from datetime import UTC, datetime

from helpers.common.date_time import resolve_timezone
from reports import repository
from reports.data_source import ReportDataSource
from reports.stats import ALL_STATS
from reports.text_variables import text_variable_catalog
from reports.validation import definition_errors
from reports.windows import resolve_window, window_length_error
from schemas.reports import BlockKind, ReportDefinition
from schemas.reports.api import (
    ReportCatalogResponse,
    ReportRunCreateRequest,
    ReportRunResponse,
    ReportRunsDeleteResponse,
    ReportRunStatus,
    ReportRunSummary,
    ReportTemplateCreateRequest,
    ReportTemplateResponse,
    ReportTemplateUpdateRequest,
)
from schemas.reports.internal import ReportSiteContext
from utils.exceptions import NotFoundError, ValidationError

BLOCK_KINDS: list[BlockKind] = ["text", "kpi", "chart", "point_stats_table", "alarm_events_table"]
AD_HOC_RUN_NAME = "Custom report"


async def _site_context(site_id: int, data_source: ReportDataSource) -> ReportSiteContext:
    context = await data_source.get_site_context(site_id)
    if context is None:
        raise NotFoundError(f"Site {site_id} not found")
    return context


def _check_definition(definition: ReportDefinition, context: ReportSiteContext) -> None:
    errors = definition_errors(definition, context)
    if errors:
        raise ValidationError(
            f"The report doesn't fit site {context.site.site_id}: {'; '.join(errors)}", payload={"errors": errors}
        )


def _resolved_window(definition: ReportDefinition, context: ReportSiteContext, now: datetime) -> tuple[datetime, datetime]:
    start, end = resolve_window(definition.window, now, resolve_timezone(context.site.timezone))
    error = window_length_error(start, end)
    if error is not None:
        raise ValidationError(error)
    return start, end


# --- Catalog -----------------------------------------------------------------------------


async def get_catalog(site_id: int, data_source: ReportDataSource) -> ReportCatalogResponse:
    context = await _site_context(site_id, data_source)
    return ReportCatalogResponse(
        site_id=site_id,
        timezone=context.site.timezone,
        block_kinds=BLOCK_KINDS,
        point_stats=list(ALL_STATS),
        site_functions=context.functions,
        text_variables=text_variable_catalog(),
    )


# --- Templates ---------------------------------------------------------------------------


async def list_templates(site_id: int, data_source: ReportDataSource) -> list[ReportTemplateResponse]:
    await _site_context(site_id, data_source)
    return await repository.list_templates(site_id)


async def get_template(site_id: int, template_id: int, data_source: ReportDataSource) -> ReportTemplateResponse:
    await _site_context(site_id, data_source)
    return await repository.get_template(site_id, template_id)


async def create_template(
    site_id: int, request: ReportTemplateCreateRequest, data_source: ReportDataSource
) -> ReportTemplateResponse:
    context = await _site_context(site_id, data_source)
    _check_definition(request.definition, context)
    if request.definition.window.kind == "fixed":
        _resolved_window(request.definition, context, datetime.now(UTC))
    return await repository.create_template(site_id, request)


async def update_template(
    site_id: int, template_id: int, request: ReportTemplateUpdateRequest, data_source: ReportDataSource
) -> ReportTemplateResponse:
    context = await _site_context(site_id, data_source)
    if request.definition is not None:
        _check_definition(request.definition, context)
        if request.definition.window.kind == "fixed":
            _resolved_window(request.definition, context, datetime.now(UTC))
    return await repository.update_template(site_id, template_id, request)


async def delete_template(site_id: int, template_id: int, data_source: ReportDataSource) -> ReportTemplateResponse:
    await _site_context(site_id, data_source)
    return await repository.delete_template(site_id, template_id)


# --- Runs --------------------------------------------------------------------------------


async def request_run(
    site_id: int, request: ReportRunCreateRequest, data_source: ReportDataSource, now: datetime
) -> ReportRunResponse:
    """Queue a report: from a template (its current definition and version) or an inline
    definition, with the window optionally replaced. The worker generates it."""
    context = await _site_context(site_id, data_source)
    template: ReportTemplateResponse | None = None
    if request.template_id is not None:
        template = await repository.get_template(site_id, request.template_id)
        definition = template.definition
    elif request.definition is not None:
        definition = request.definition
    else:  # unreachable: ReportRunCreateRequest requires one of the two
        raise ValidationError("Give exactly one of template_id and definition")
    if request.window is not None:
        definition = definition.model_copy(update={"window": request.window})
    _check_definition(definition, context)
    window_start, window_end = _resolved_window(definition, context, now)
    return await repository.insert_run(
        site_id,
        name=request.name or (template.name if template is not None else AD_HOC_RUN_NAME),
        definition=definition,
        window_start=window_start,
        window_end=window_end,
        trigger="manual",
        template_id=template.id if template is not None else None,
        template_version=template.version if template is not None else None,
    )


async def rerun(site_id: int, run_id: int, data_source: ReportDataSource) -> ReportRunResponse:
    """Queue the same report again: same definition and the same window, generated from the current
    data (e.g. after late readings arrived)."""
    context = await _site_context(site_id, data_source)
    previous = await repository.get_run(site_id, run_id)
    _check_definition(previous.definition, context)
    return await repository.insert_run(
        site_id,
        name=previous.name,
        definition=previous.definition,
        window_start=previous.window_start,
        window_end=previous.window_end,
        trigger="manual",
        template_id=previous.template_id,
        template_version=previous.template_version,
    )


async def list_runs(
    site_id: int, data_source: ReportDataSource, template_id: int | None = None,
    status: ReportRunStatus | None = None, limit: int = 50, schedule_id: int | None = None,
) -> list[ReportRunSummary]:
    await _site_context(site_id, data_source)
    return await repository.list_runs(site_id, template_id=template_id, status=status, limit=limit, schedule_id=schedule_id)


async def get_run(site_id: int, run_id: int, data_source: ReportDataSource) -> ReportRunResponse:
    await _site_context(site_id, data_source)
    return await repository.get_run(site_id, run_id)


async def delete_runs(site_id: int, data_source: ReportDataSource) -> ReportRunsDeleteResponse:
    await _site_context(site_id, data_source)
    return ReportRunsDeleteResponse(deleted=await repository.delete_runs(site_id))


async def delete_run(site_id: int, run_id: int, data_source: ReportDataSource) -> ReportRunSummary:
    await _site_context(site_id, data_source)
    return await repository.delete_run(site_id, run_id)
