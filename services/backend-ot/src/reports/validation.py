"""Checking a report definition against its site: every point, device and site function it names
must exist there and fit where it is used. Pure: works on a ReportSiteContext."""

from reports.text_variables import text_variable_errors
from schemas.reports import (
    AlarmEventsTableBlock,
    ChartBlock,
    KpiBlock,
    PointSeries,
    PointStatKpi,
    PointStatsTableBlock,
    ReportDefinition,
    SiteFunctionKpi,
    SiteFunctionSeries,
    TextBlock,
)
from schemas.reports.internal import ReportSiteContext


def definition_errors(definition: ReportDefinition, context: ReportSiteContext) -> list[str]:
    """Every problem with the definition on this site, each prefixed with its block id; empty if
    it can be generated."""
    errors: list[str] = []
    for block in definition.blocks:
        errors += [f"{block.id}: {error}" for error in _block_errors(block, context)]
    return errors


def _block_errors(
    block: TextBlock | KpiBlock | ChartBlock | PointStatsTableBlock | AlarmEventsTableBlock,
    context: ReportSiteContext,
) -> list[str]:
    match block:
        case TextBlock(body=body):
            return text_variable_errors(body, context)
        case KpiBlock(items=items):
            errors: list[str] = []
            for item in items:
                if isinstance(item, PointStatKpi):
                    errors += _point_errors([item.point_id], context)
                else:
                    errors += _kpi_function_errors(item, context)
            return errors
        case ChartBlock(series=series):
            errors = []
            for source in series:
                if isinstance(source, PointSeries):
                    errors += _point_errors([source.point_id], context)
                else:
                    errors += _series_function_errors(source, context)
            return errors
        case PointStatsTableBlock(point_ids=point_ids):
            return _point_errors(point_ids, context)
        case AlarmEventsTableBlock(device_ids=device_ids):
            return [f"device {device_id} is not on this site" for device_id in device_ids if context.find_device(device_id) is None]
    return [f"unknown block kind {block!r}"]


def _point_errors(point_ids: list[int], context: ReportSiteContext) -> list[str]:
    return [f"point {point_id} is not on this site" for point_id in point_ids if context.find_point(point_id) is None]


def _function_errors(name: str, device_id: int | None, context: ReportSiteContext) -> list[str]:
    function = context.find_function(name)
    if function is None:
        return [f"site function '{name}' is not offered by this site"]
    if function.kind != "device":
        return [f"site function '{name}' is site-wide: remove device_id"] if device_id is not None else []
    if device_id is None:
        return [f"site function '{name}' is a device function: give a device_id"]
    device = context.find_device(device_id)
    if device is None:
        return [f"device {device_id} is not on this site"]
    if function.device_types and device.type not in function.device_types:
        return [f"site function '{name}' does not apply to device {device_id} ({device.type})"]
    return []


def _kpi_function_errors(item: SiteFunctionKpi, context: ReportSiteContext) -> list[str]:
    errors = _function_errors(item.function, item.device_id, context)
    function = context.find_function(item.function)
    if not errors and function is not None and item.field not in function.numeric_fields:
        available = ", ".join(function.numeric_fields) or "none"
        errors.append(f"site function '{item.function}' has no numeric field '{item.field}' (available: {available})")
    return errors


def _series_function_errors(source: SiteFunctionSeries, context: ReportSiteContext) -> list[str]:
    errors = _function_errors(source.function, source.device_id, context)
    function = context.find_function(source.function)
    if not errors and function is not None and function.output != "series":
        errors.append(f"site function '{source.function}' returns no series: use it in a kpi block")
    return errors
