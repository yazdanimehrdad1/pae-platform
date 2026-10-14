"""chart: point readings and series site functions over the window, sampled for a chart."""

from pydantic import BaseModel

from reports.blocks.context import BlockContext
from schemas.api_models import PointTimeseries
from schemas.reports import ChartBlock, ChartResult, PointSeries, SiteFunctionSeries


async def resolve_chart(block: ChartBlock, context: BlockContext) -> ChartResult:
    """Series in the block's order. A point without readings in the window gets an empty series,
    so the chart still names it."""
    point_ids = [source.point_id for source in block.series if isinstance(source, PointSeries)]
    point_series = {
        series.id: series
        for series in await context.data_source.get_point_series(
            context.site_id, point_ids, context.window_start, context.window_end, block.max_points
        )
    }
    series: list[PointTimeseries] = []
    for source in block.series:
        if isinstance(source, PointSeries):
            series.append(point_series.get(source.point_id) or _empty_series(source.point_id, context))
        else:
            series += await _function_series(source, block.max_points, context)
    return ChartResult(block_id=block.id, title=block.title, style=block.style, series=series)


def _empty_series(point_id: int, context: BlockContext) -> PointTimeseries:
    found = context.site.find_point(point_id)
    if found is None:
        return PointTimeseries(id=point_id, name=f"point {point_id}", data_type="float32")
    point, _ = found
    return PointTimeseries(
        id=point.id, name=point.name, data_type=point.data_type, unit=point.unit,
        point_class=point.point_class, severity=point.severity,
    )


async def _function_series(source: SiteFunctionSeries, max_points: int, context: BlockContext) -> list[PointTimeseries]:
    result = await context.data_source.run_site_function(
        context.site_id, source.function, context.window_start, context.window_end,
        device_id=source.device_id, max_points=max_points,
    )
    return series_of(result)


def series_of(result: BaseModel) -> list[PointTimeseries]:
    """The `series` field of a series function's result: one PointTimeseries or a list of them."""
    value = getattr(result, "series", None)
    if isinstance(value, PointTimeseries):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, PointTimeseries)]
    return []
