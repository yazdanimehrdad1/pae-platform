"""Read-only tools over one site's devices, points and readings. The site always comes from the
request context, never from Claude's arguments, so a tool cannot reach another site."""

from collections.abc import Sequence
from datetime import timedelta

from pydantic import AwareDatetime, Field

from intelli_gateway.interfaces.knowledge_store import KnowledgeStore
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.knowledge.guides import applicable_guidance
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.knowledge import GuideSeverity
from intelli_gateway.schemas.site_data import HistorySample
from intelli_gateway.schemas.tools import JSONValue, ToolInput
from intelli_gateway.tools.base import ToolDefinition, ToolError, tool
from intelli_gateway.tools.common import (
    SiteToolLimits,
    dump,
    guidance_entry,
    is_discrete,
    resolve_point,
    site_id_of,
)

MAX_VALUES_PER_CALL = 20


class NoInput(ToolInput):
    pass


class ListPointsInput(ToolInput):
    filter: str | None = Field(
        default=None,
        description="Case-insensitive text matched against point name, description, device "
        "and equipment type, e.g. 'INV2', 'temperature', 'alarm'. Omit to list all points.",
    )
    device_id: int | None = Field(default=None, description="Only points of this device.")


class PointValuesInput(ToolInput):
    point_names: list[str] = Field(
        min_length=1,
        max_length=MAX_VALUES_PER_CALL,
        description="Exact point names as returned by list_points.",
    )


class PointHistoryInput(ToolInput):
    point_name: str = Field(description="Exact point name as returned by list_points.")
    start: AwareDatetime = Field(description="Start of the window, ISO 8601 with a UTC offset.")
    end: AwareDatetime = Field(description="End of the window, ISO 8601 with a UTC offset.")


class DeviceInput(ToolInput):
    device_id: int = Field(description="Device id as returned by get_site_overview.")


def summarize_history(samples: Sequence[HistorySample], sample_count: int) -> dict[str, JSONValue]:
    """min/max/avg/first/last plus a few evenly spaced samples."""
    if not samples:
        return {"count": 0}
    values = [sample.value for sample in samples]
    if len(samples) <= sample_count:
        picked = list(samples)
    else:
        step = (len(samples) - 1) / (sample_count - 1)
        picked = [samples[round(index * step)] for index in range(sample_count)]
    return {
        "count": len(samples),
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 3),
        "first": {"timestamp": samples[0].timestamp.isoformat(), "value": samples[0].value},
        "last": {"timestamp": samples[-1].timestamp.isoformat(), "value": samples[-1].value},
        "samples": [
            {"timestamp": sample.timestamp.isoformat(), "value": sample.value} for sample in picked
        ],
    }


def build_site_tools(
    site_data: SiteDataConnector, knowledge: KnowledgeStore, limits: SiteToolLimits
) -> list[ToolDefinition]:
    @tool(
        name="get_site_overview",
        description="""
Start here. Returns the site (name, capacity, time zone), its devices (id, name, type, vendor,
model, whether each is still reporting), the electrical topology (which equipment connects to
which) and how many alarms are active right now.
""",
        input_model=NoInput,
    )
    async def get_site_overview(args: NoInput, ctx: RequestContext) -> JSONValue:
        site_id = site_id_of(ctx)
        site = await site_data.get_site(site_id)
        if site is None:
            raise ToolError("site not found")
        comms = {entry.device_id: entry for entry in await site_data.get_device_comms(site_id)}
        devices: list[JSONValue] = []
        for device in await site_data.list_devices(site_id):
            row = dump(device)
            status = comms.get(device.device_id)
            if status is not None:
                row["last_reading_at"] = (
                    status.last_reading_at.isoformat() if status.last_reading_at else None
                )
                row["stale"] = status.stale
            devices.append(row)
        topology = await site_data.get_topology(site_id)
        node_names = {node.node_id: node.name for node in topology.nodes}
        active = await site_data.get_active_alarms(site_id)
        return {
            "site": dump(site),
            "devices": devices,
            "topology": {
                "nodes": [dump(node) for node in topology.nodes],
                "connections": [
                    f"{node_names.get(link.from_id, link.from_id)} -- "
                    f"{node_names.get(link.to_id, link.to_id)}"
                    for link in topology.connections
                ],
            },
            "active_alarm_events": len(active.events),
            "active_alarm_points": len(active.point_alarms),
        }

    @tool(
        name="list_points",
        description="""
Search this site's data point catalog. Use it to find the exact point names the other tools
need. Each row has the name, description, unit, device, equipment type, point class (ANALOG,
BINARY = status, ALARM, CONTROL), whether its values have labels (enum or bits) and whether an
engineer guide exists for it (has_guide: then explain_point and lookup_fault can tell you what
it means). Returns at most a fixed number of rows plus the total match count.
""",
        input_model=ListPointsInput,
    )
    async def list_points(args: ListPointsInput, ctx: RequestContext) -> JSONValue:
        site_id = site_id_of(ctx)
        points = await site_data.list_points(site_id)
        if args.device_id is not None:
            points = [point for point in points if point.device_id == args.device_id]
        if args.filter:
            needle = args.filter.lower()
            points = [
                point
                for point in points
                if needle
                in " ".join(
                    filter(
                        None,
                        [point.name, point.description, point.device_name, point.equipment],
                    )
                ).lower()
            ]
        guided = {
            (guide.device_id, guide.point_name)
            for guide in await knowledge.list_point_guides(site_id)
        }
        rows: list[JSONValue] = []
        for point in points[: limits.max_rows]:
            row: dict[str, JSONValue] = {
                "name": point.name,
                "description": point.description,
                "unit": point.unit,
                "device_id": point.device_id,
                "device_name": point.device_name,
                "equipment": point.equipment,
                "point_class": point.point_class.value if point.point_class else None,
                "labels": "enum" if point.enum_labels else "bits" if point.bit_labels else None,
                "has_guide": (point.device_id, point.name) in guided,
            }
            rows.append({key: value for key, value in row.items() if value is not None})
        return {"total_matches": len(points), "returned": len(rows), "points": rows}

    @tool(
        name="get_point_values",
        description=f"""
Get the latest values of up to {MAX_VALUES_PER_CALL} points in one call: value, unit,
timestamp and age in seconds. Status points also return their label; alarm words return the
labels of the set bits (active_bits). "stale": true means the point has not updated recently:
its device may have stopped reporting. Ask for all the points you need at once.
""",
        input_model=PointValuesInput,
    )
    async def get_point_values(args: PointValuesInput, ctx: RequestContext) -> JSONValue:
        latest = await site_data.get_latest_many(site_id_of(ctx), args.point_names)
        values: list[JSONValue] = [dump(value) for value in latest.values() if value is not None]
        missing: list[JSONValue] = [name for name, value in latest.items() if value is None]
        result: dict[str, JSONValue] = {"values": values}
        if missing:
            result["not_found"] = missing
            result["hint"] = "call list_points to see valid names"
        return result

    @tool(
        name="get_point_history",
        description="""
Get the history of one point between start and end, as a summary rather than raw rows.
- Measurements: count, min, max, average, first and last value, and a few evenly spaced
  samples.
- Status, alarm and fault-code points: the list of changes (time, value, label or set bits),
  starting with the value at `start`. Use it to see when a state began or how often it
  toggles.
Use it for trends, comparisons and "what happened" questions. The maximum window is limited.
""",
        input_model=PointHistoryInput,
    )
    async def get_point_history(args: PointHistoryInput, ctx: RequestContext) -> JSONValue:
        if args.end <= args.start:
            raise ToolError("end must be after start")
        if args.end - args.start > timedelta(days=limits.history_max_days):
            raise ToolError(
                f"window longer than {limits.history_max_days} days",
                hint="split the question into shorter windows",
            )
        site_id = site_id_of(ctx)
        point = await resolve_point(site_data, site_id, args.point_name)
        window: dict[str, JSONValue] = {
            "point_name": args.point_name,
            "start": args.start.isoformat(),
            "end": args.end.isoformat(),
        }
        if is_discrete(point):
            changes = await site_data.get_state_changes(site_id, point.name, args.start, args.end)
            changes = changes or []
            kept = changes[-limits.max_rows :]
            return {
                **window,
                "kind": "state_changes",
                "total_changes": len(changes),
                "changes": [dump(change) for change in kept],
                **(
                    {"truncated": "only the most recent changes are listed"}
                    if len(kept) < len(changes)
                    else {}
                ),
            }
        samples = await site_data.get_history(site_id, point.name, args.start, args.end) or []
        return {
            **window,
            "kind": "summary",
            "unit": point.unit,
            **summarize_history(samples, limits.history_samples),
        }

    @tool(
        name="get_device_status",
        description="""
One device at a glance: its details, whether it is still reporting (last reading, stale), the
current value of each of its points (with labels), its active alarm events, and the engineer
guide entries that apply right now (warnings and faults with probable causes and checks).
Use it when a question is about one device, or after get_active_alarms points at a device.
""",
        input_model=DeviceInput,
    )
    async def get_device_status(args: DeviceInput, ctx: RequestContext) -> JSONValue:
        site_id = site_id_of(ctx)
        device = next(
            (d for d in await site_data.list_devices(site_id) if d.device_id == args.device_id),
            None,
        )
        if device is None:
            raise ToolError("device not found", hint="call get_site_overview to see device ids")
        points = [
            p for p in await site_data.list_points(site_id) if p.device_id == device.device_id
        ]
        latest = await site_data.get_latest_many(site_id, [point.name for point in points])
        comms = next(
            (
                c
                for c in await site_data.get_device_comms(site_id)
                if c.device_id == device.device_id
            ),
            None,
        )
        guidance: list[JSONValue] = []
        for point in points:
            reading = latest.get(point.name)
            guide = await knowledge.get_point_guide(site_id, device.device_id, point.name)
            if reading is None or guide is None:
                continue
            guidance.extend(
                guidance_entry(point.name, entry)
                for entry in applicable_guidance(guide, reading)
                if entry.severity is not GuideSeverity.INFO
            )
        active = await site_data.get_active_alarms(site_id)
        return {
            "device": dump(device),
            "comms": dump(comms) if comms else None,
            "values": [dump(value) for value in list(latest.values())[: limits.max_rows] if value],
            "active_alarm_events": [
                dump(event) for event in active.events if event.device_id == device.device_id
            ],
            "guidance": guidance,
        }

    return [get_site_overview, list_points, get_point_values, get_point_history, get_device_status]
