"""kpi: headline numbers from point statistics and site function results."""

from pydantic import BaseModel

from reports.blocks.context import BlockContext
from reports.blocks.errors import block_error_message
from schemas.reports import KpiBlock, KpiResult, KpiValue, PointStatKpi, SiteFunctionKpi

# Unit of a site function's result field, from the field's name suffix.
_FIELD_UNIT_SUFFIXES = (("_mwh", "MWh"), ("_kwh", "kWh"), ("_mw", "MW"), ("_kw", "kW"), ("_pct", "%"), ("_hours", "h"))


def unit_for_field(field: str) -> str | None:
    return next((unit for suffix, unit in _FIELD_UNIT_SUFFIXES if field.endswith(suffix)), None)


async def resolve_kpi(block: KpiBlock, context: BlockContext) -> KpiResult:
    point_stats = await _point_stats(block, context)
    function_results: dict[tuple[str, int | None], BaseModel | str] = {}
    items: list[KpiValue] = []
    for item in block.items:
        if isinstance(item, PointStatKpi):
            items.append(_point_stat_value(item, point_stats, context))
        else:
            key = (item.function, item.device_id)
            if key not in function_results:
                function_results[key] = await _run_function(item, context)
            items.append(_function_value(item, function_results[key]))
    return KpiResult(block_id=block.id, title=block.title, items=items)


async def _point_stats(block: KpiBlock, context: BlockContext) -> dict[int, dict[str, float | None]]:
    point_ids = sorted({item.point_id for item in block.items if isinstance(item, PointStatKpi)})
    stats = await context.data_source.get_point_stats(
        context.site_id, point_ids, context.window_start, context.window_end, "none", context.site_timezone.key
    )
    return {entry.point_id: dict(entry.values) for entry in stats}


def _point_stat_value(item: PointStatKpi, stats: dict[int, dict[str, float | None]], context: BlockContext) -> KpiValue:
    found = context.site.find_point(item.point_id)
    point_name = found[0].name if found else f"point {item.point_id}"
    unit = found[0].unit if found and item.stat != "count" else None
    value = stats.get(item.point_id, {}).get(item.stat)
    if value is None and item.stat == "count":
        value = 0.0
    return KpiValue(label=item.label or f"{point_name} {item.stat}", value=value, unit=unit)


async def _run_function(item: SiteFunctionKpi, context: BlockContext) -> BaseModel | str:
    """The function's result, or why it failed (one failing function doesn't fail the block)."""
    try:
        return await context.data_source.run_site_function(
            context.site_id, item.function, context.window_start, context.window_end, device_id=item.device_id
        )
    except Exception as error:
        return block_error_message(error, f"site function '{item.function}'")


def _function_value(item: SiteFunctionKpi, result: BaseModel | str) -> KpiValue:
    label = item.label or item.field
    unit = unit_for_field(item.field)
    if isinstance(result, str):
        return KpiValue(label=label, unit=unit, error=result)
    value = getattr(result, item.field, None)
    if value is not None and not isinstance(value, int | float):
        return KpiValue(label=label, unit=unit, error=f"'{item.field}' is not a number")
    return KpiValue(label=label, value=float(value) if value is not None else None, unit=unit)
