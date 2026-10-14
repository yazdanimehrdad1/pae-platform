"""
Block resolvers: one per block kind, each turning a definition block into its stored result.

To add a block kind: its definition model (schemas/reports/definition.py, added to ReportBlock),
its result model (schemas/reports/snapshot.py, added to BlockResult), its checks
(reports/validation.py), a resolver module here, and one RESOLVERS entry below.
"""

from collections.abc import Awaitable, Callable

from reports.blocks.alarm_events_table import resolve_alarm_events_table
from reports.blocks.chart import resolve_chart
from reports.blocks.context import BlockContext
from reports.blocks.errors import block_error_message
from reports.blocks.kpi import resolve_kpi
from reports.blocks.point_stats_table import resolve_point_stats_table
from reports.blocks.text import resolve_text
from schemas.reports import (
    AlarmEventsTableBlock,
    AlarmEventsTableResult,
    BlockResult,
    ChartBlock,
    ChartResult,
    KpiBlock,
    KpiResult,
    PointStatsTableBlock,
    PointStatsTableResult,
    ReportBlock,
    TextBlock,
    TextResult,
)

# Block model -> (its resolver, its result model, used for a result that carries only an error).
RESOLVERS: dict[type, tuple[Callable[..., Awaitable[BlockResult]], type]] = {
    TextBlock: (resolve_text, TextResult),
    KpiBlock: (resolve_kpi, KpiResult),
    ChartBlock: (resolve_chart, ChartResult),
    PointStatsTableBlock: (resolve_point_stats_table, PointStatsTableResult),
    AlarmEventsTableBlock: (resolve_alarm_events_table, AlarmEventsTableResult),
}


async def resolve_block(block: ReportBlock, context: BlockContext) -> BlockResult:
    """The block's result; if it fails, a result of the same kind with `error` set, so the rest of
    the report still generates."""
    resolver, result_model = RESOLVERS[type(block)]
    try:
        return await resolver(block, context)
    except Exception as error:
        return result_model(block_id=block.id, title=block.title, error=block_error_message(error, f"block '{block.id}'"))


__all__ = ["RESOLVERS", "BlockContext", "resolve_block"]
