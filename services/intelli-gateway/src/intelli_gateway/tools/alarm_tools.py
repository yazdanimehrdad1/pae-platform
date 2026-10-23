"""Read-only alarm tools: what is active now, and the raise/clear timeline."""

from datetime import timedelta

from pydantic import AwareDatetime, Field

from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.site_data import AlarmEvent
from intelli_gateway.schemas.tools import JSONValue, ToolInput
from intelli_gateway.tools.base import ToolDefinition, ToolError, tool
from intelli_gateway.tools.common import SiteToolLimits, dump, site_id_of


class NoInput(ToolInput):
    pass


class AlarmHistoryInput(ToolInput):
    start: AwareDatetime = Field(description="Start of the window, ISO 8601 with a UTC offset.")
    end: AwareDatetime = Field(description="End of the window, ISO 8601 with a UTC offset.")
    device_id: int | None = Field(default=None, description="Only alarms of this device.")


def _event_row(event: AlarmEvent, device_names: dict[int, str]) -> dict[str, JSONValue]:
    row = dump(event)
    if event.device_id is not None:
        row["device_name"] = device_names.get(event.device_id)
    if event.cleared_at is not None:
        row["duration_min"] = round((event.cleared_at - event.raised_at).total_seconds() / 60)
    return row


def build_alarm_tools(site_data: SiteDataConnector, limits: SiteToolLimits) -> list[ToolDefinition]:
    async def device_names(site_id: int) -> dict[int, str]:
        return {device.device_id: device.name for device in await site_data.list_devices(site_id)}

    @tool(
        name="get_active_alarms",
        description="""
What is wrong right now. Returns active alarm events (name, severity fault/warning, message,
device, raised time) and alarm points with a non-zero value (alarm words with the labels of
their set bits, vendor fault codes). Use it early when troubleshooting. Then use
lookup_fault on an alarm bit or fault code to get its meaning, probable causes and checks.
""",
        input_model=NoInput,
    )
    async def get_active_alarms(args: NoInput, ctx: RequestContext) -> JSONValue:
        site_id = site_id_of(ctx)
        active = await site_data.get_active_alarms(site_id)
        names = await device_names(site_id)
        return {
            "events": [_event_row(event, names) for event in active.events],
            "point_alarms": [
                {**dump(alarm), "device_name": names.get(alarm.device_id)}
                for alarm in active.point_alarms
            ],
        }

    @tool(
        name="get_alarm_history",
        description="""
Alarm events (raised and cleared, with durations) that were active at any time between start
and end, optionally for one device. Use it to see whether a problem is new or recurring, and
what happened around a given time. Returns the most recent events if there are many.
""",
        input_model=AlarmHistoryInput,
    )
    async def get_alarm_history(args: AlarmHistoryInput, ctx: RequestContext) -> JSONValue:
        if args.end <= args.start:
            raise ToolError("end must be after start")
        if args.end - args.start > timedelta(days=limits.history_max_days):
            raise ToolError(
                f"window longer than {limits.history_max_days} days",
                hint="split the question into shorter windows",
            )
        site_id = site_id_of(ctx)
        events = await site_data.get_alarm_events(site_id, args.start, args.end, args.device_id)
        names = await device_names(site_id)
        kept = events[-limits.max_rows :]
        result: dict[str, JSONValue] = {
            "total_events": len(events),
            "events": [_event_row(event, names) for event in kept],
        }
        if len(kept) < len(events):
            result["truncated"] = "only the most recent events are listed"
        return result

    return [get_active_alarms, get_alarm_history]
