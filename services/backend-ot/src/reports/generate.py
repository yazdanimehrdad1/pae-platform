"""Generating a report: resolve every block of a definition over a window into a ReportSnapshot."""

from datetime import datetime

from helpers.common.date_time import resolve_timezone
from reports.blocks import BlockContext, resolve_block
from reports.data_source import ReportDataSource
from schemas.reports import ReportDefinition, ReportSnapshot
from schemas.reports.internal import ReportSiteContext


async def generate_snapshot(
    definition: ReportDefinition,
    site: ReportSiteContext,
    window_start: datetime,
    window_end: datetime,
    generated_at: datetime,
    data_source: ReportDataSource,
) -> ReportSnapshot:
    """Blocks resolve one after another, in order (each reads the database; doing them in turn keeps
    one report from holding several connections). A failing block carries its error."""
    site_timezone = resolve_timezone(site.site.timezone)
    context = BlockContext(
        site=site, window_start=window_start, window_end=window_end,
        site_timezone=site_timezone, data_source=data_source,
    )
    return ReportSnapshot(
        site_id=site.site.site_id,
        site_name=site.site.name,
        timezone=site_timezone.key,
        window_start=window_start,
        window_end=window_end,
        generated_at=generated_at,
        definition=definition,
        blocks=[await resolve_block(block, context) for block in definition.blocks],
    )
