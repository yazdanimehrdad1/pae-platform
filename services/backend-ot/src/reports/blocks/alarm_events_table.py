"""alarm_events_table: the alarm events that overlap the window."""

from reports.blocks.context import BlockContext
from schemas.reports import AlarmEventRow, AlarmEventsTableBlock, AlarmEventsTableResult


async def resolve_alarm_events_table(block: AlarmEventsTableBlock, context: BlockContext) -> AlarmEventsTableResult:
    """Newest raise first, at most `limit` rows; total_count says how many matched. An event still
    active at the window end lasts until the window end."""
    events = await context.data_source.get_alarm_events(
        context.site_id, context.window_start, context.window_end, severity=block.severity
    )
    if block.device_ids:
        wanted = set(block.device_ids)
        events = [event for event in events if event.device_id in wanted]
    names = await context.data_source.get_alarm_names(context.site_id)
    device_names = {device.device_id: device.name for device in context.site.devices}

    rows = []
    for event in events[: block.limit]:
        ended = event.cleared_at if event.cleared_at is not None else context.window_end
        rows.append(AlarmEventRow(
            event_id=event.id,
            alarm_name=names.get(event.definition_id, f"alarm {event.definition_id}"),
            severity=event.severity,
            device_id=event.device_id,
            device_name=device_names.get(event.device_id) if event.device_id is not None else None,
            raised_at=event.raised_at,
            cleared_at=event.cleared_at,
            duration_seconds=max((ended - event.raised_at).total_seconds(), 0.0),
            value_at_raise=event.value_at_raise,
            message=event.message,
        ))
    return AlarmEventsTableResult(block_id=block.id, title=block.title, rows=rows, total_count=len(events))
