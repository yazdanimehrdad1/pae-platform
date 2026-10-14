"""point_stats_table: statistics per point, for the whole window or per local hour/day."""

from reports.blocks.context import BlockContext
from schemas.reports import PointStatsRow, PointStatsTableBlock, PointStatsTableResult
from schemas.reports.internal import PointStatValues


async def resolve_point_stats_table(block: PointStatsTableBlock, context: BlockContext) -> PointStatsTableResult:
    """Rows by point (in the block's order), then by bucket. A point without readings still gets
    one row, with empty values, so the table names it."""
    stats = await context.data_source.get_point_stats(
        context.site_id, block.point_ids, context.window_start, context.window_end,
        block.bucket, context.site_timezone.key,
    )
    by_point: dict[int, list[PointStatValues]] = {}
    for entry in stats:
        by_point.setdefault(entry.point_id, []).append(entry)

    rows: list[PointStatsRow] = []
    for point_id in block.point_ids:
        entries = sorted(by_point.get(point_id, []), key=lambda entry: entry.bucket_start or context.window_start)
        for entry in entries or [PointStatValues(point_id=point_id)]:
            rows.append(_row(point_id, entry, block, context))
    return PointStatsTableResult(block_id=block.id, title=block.title, stats=block.stats, bucket=block.bucket, rows=rows)


def _row(point_id: int, entry: PointStatValues, block: PointStatsTableBlock, context: BlockContext) -> PointStatsRow:
    found = context.site.find_point(point_id)
    values = {stat: entry.values.get(stat) for stat in block.stats}
    if "count" in values and values["count"] is None:
        values["count"] = 0.0
    if found is None:
        return PointStatsRow(
            point_id=point_id, point_name=f"point {point_id}", device_id=0, device_name="",
            bucket_start=entry.bucket_start, values=values,
        )
    point, device = found
    return PointStatsRow(
        point_id=point.id, point_name=point.name, device_id=device.device_id, device_name=device.name,
        unit=point.unit, bucket_start=entry.bucket_start, values=values,
    )
