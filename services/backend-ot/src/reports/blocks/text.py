"""text: a paragraph with its variables (site, devices, points) filled in (reports.text_variables)."""

from datetime import datetime

from reports.blocks.context import BlockContext
from reports.text_variables import render_text, stat_point_ids
from schemas.reports import TextBlock, TextResult


async def resolve_text(block: TextBlock, context: BlockContext) -> TextResult:
    point_ids = stat_point_ids(block.body)
    stats = await context.data_source.get_point_stats(
        context.site_id, point_ids, context.window_start, context.window_end, "none", context.site_timezone.key
    ) if point_ids else []
    body = render_text(
        block.body, context.site, context.window_start, context.window_end, context.site_timezone.key,
        lambda time: _local(time, context), stats,
    )
    return TextResult(block_id=block.id, title=block.title, body=body)


def _local(time: datetime, context: BlockContext) -> str:
    return time.astimezone(context.site_timezone).strftime("%Y-%m-%d %H:%M")
