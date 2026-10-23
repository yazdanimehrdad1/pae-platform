"""Read-only tools over engineer-written knowledge: point guides, fault lookups, IM scripts and
experience notes."""

from typing import Self

from pydantic import Field, model_validator

from intelli_gateway.interfaces.knowledge_store import KnowledgeStore
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.knowledge.guides import applicable_guidance
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.knowledge import StateGuide
from intelli_gateway.schemas.tools import JSONValue, ToolInput
from intelli_gateway.tools.base import ToolDefinition, ToolError, tool
from intelli_gateway.tools.bounds import truncate_text
from intelli_gateway.tools.common import (
    SiteToolLimits,
    dump,
    guidance_entry,
    resolve_point,
    site_id_of,
)


class PointNameInput(ToolInput):
    point_name: str = Field(description="Exact point name as returned by list_points.")


class LookupFaultInput(ToolInput):
    point_name: str = Field(
        description="The status, alarm-word or fault-code point, e.g. 'INV2.FaultCode'."
    )
    code: int | None = Field(
        default=None,
        description="The enum value, the bit index (0 = least significant) or the vendor fault "
        "code.",
    )
    label: str | None = Field(
        default=None, description="Or the label instead of the code, e.g. 'OVER_TEMP'."
    )

    @model_validator(mode="after")
    def code_or_label(self) -> Self:
        if self.code is None and not self.label:
            raise ValueError("give a code or a label")
        return self


class DeviceScriptInput(ToolInput):
    device_id: int = Field(description="Device id as returned by list_points or get_site_overview.")


class SearchNotesInput(ToolInput):
    keywords: list[str] = Field(
        min_length=1,
        max_length=10,
        description="Words to look for in engineers' experience notes, e.g. ['INV2', 'derating'].",
    )
    device_id: int | None = Field(default=None, description="Only notes about this device.")


def _state_summary(state: StateGuide) -> dict[str, JSONValue]:
    return {
        "kind": state.kind.value,
        "code": state.code,
        "label": state.label,
        "severity": state.severity.value,
        "message": state.message,
    }


def build_knowledge_tools(
    site_data: SiteDataConnector, knowledge: KnowledgeStore, limits: SiteToolLimits
) -> list[ToolDefinition]:
    @tool(
        name="explain_point",
        description="""
What a point means, from the engineers' guide: meaning, unit and sign notes, normal range,
limits (e.g. above 60 degC = derating), related points to check together, and the list of
its states or alarm bits. Also returns the current value and the guide entries that apply to
it right now, with probable causes and checks. Use it before interpreting an unfamiliar
point or value.
""",
        input_model=PointNameInput,
    )
    async def explain_point(args: PointNameInput, ctx: RequestContext) -> JSONValue:
        site_id = site_id_of(ctx)
        point = await resolve_point(site_data, site_id, args.point_name)
        reading = (await site_data.get_latest_many(site_id, [point.name])).get(point.name)
        guide = await knowledge.get_point_guide(site_id, point.device_id, point.name)
        result: dict[str, JSONValue] = {
            "point": dump(point),
            "current": dump(reading) if reading else None,
        }
        if guide is None:
            result["guide"] = None
            result["note"] = (
                "No engineer guide for this point. Its meaning is only what the catalog entry "
                "says; say so if it matters to the answer."
            )
            return result
        result["guide"] = {
            "meaning": guide.meaning,
            "unit_note": guide.unit_note,
            "normal_range": dump(guide.normal_range) if guide.normal_range else None,
            "related_points": list(guide.related_points),
            "limits": [dump(limit) for limit in guide.limits],
            "states": [_state_summary(state) for state in guide.states],
            "author": guide.author,
            "updated_at": guide.updated_at.isoformat(),
        }
        if reading is not None:
            result["applies_now"] = [
                guidance_entry(point.name, entry) for entry in applicable_guidance(guide, reading)
            ]
        return result

    @tool(
        name="lookup_fault",
        description="""
Look up one state, alarm bit or vendor fault code of a point in the engineers' guide: its
message, severity, meaning, probable causes, checks to recommend, related points and safety
notes. Give the code (enum value, bit index or fault code) or the label. Use it for every
alarm bit or fault code you need to explain.
""",
        input_model=LookupFaultInput,
    )
    async def lookup_fault(args: LookupFaultInput, ctx: RequestContext) -> JSONValue:
        site_id = site_id_of(ctx)
        point = await resolve_point(site_data, site_id, args.point_name)
        guide = await knowledge.get_point_guide(site_id, point.device_id, point.name)
        if guide is None or not guide.states:
            raise ToolError(
                "no engineer guide with states for this point",
                hint="only the labels in list_points are known; say the meaning is unknown",
            )
        state = guide.find_state(code=args.code, label=args.label)
        if state is None:
            known = ", ".join(f"{s.code}={s.label}" for s in guide.states[: limits.max_rows])
            raise ToolError(
                "this code or label is not in the guide",
                hint=f"known entries: {known}. An unknown vendor code needs the vendor manual.",
            )
        return {"point_name": point.name, "device_id": point.device_id, **dump(state)}

    @tool(
        name="get_device_script",
        description="""
Get the information model (IM) script of one device: how its raw registers map to data points
(addresses, data types, scaling, enums, bits, poll rate). Use it when a value looks wrong
(scaling, units, sign) or to understand a device's integration.
""",
        input_model=DeviceScriptInput,
    )
    async def get_device_script(args: DeviceScriptInput, ctx: RequestContext) -> JSONValue:
        document = await knowledge.get_device_script(site_id_of(ctx), args.device_id)
        if document is None:
            raise ToolError(
                "no IM script for this device", hint="call get_site_overview to see device ids"
            )
        return {
            "device_id": args.device_id,
            "title": document.title,
            "updated_at": document.updated_at.isoformat(),
            "script": truncate_text(document.body, limits.max_text_chars),
        }

    @tool(
        name="search_experience_notes",
        description="""
Keyword search over experience notes that engineers wrote about this site: past incidents,
root causes, workarounds and checks. Matches the note title, text and the points it is about;
optionally only notes about one device. Use it when troubleshooting, before guessing a cause.
Returns the best-matching notes (title, author, date, text).
""",
        input_model=SearchNotesInput,
    )
    async def search_experience_notes(args: SearchNotesInput, ctx: RequestContext) -> JSONValue:
        notes = await knowledge.search_notes(
            site_id_of(ctx), args.keywords, limits.max_rows, device_id=args.device_id
        )
        rows: list[JSONValue] = [
            {
                "title": note.title,
                "author": note.author,
                "device_id": note.device_id,
                "updated_at": note.updated_at.isoformat(),
                "text": truncate_text(note.body, limits.max_text_chars),
            }
            for note in notes
        ]
        return {"matches": len(rows), "notes": rows}

    return [explain_point, lookup_fault, get_device_script, search_experience_notes]
