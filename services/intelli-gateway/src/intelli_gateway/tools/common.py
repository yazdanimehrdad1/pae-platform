"""Helpers shared by the tool modules."""

from dataclasses import dataclass

from pydantic import BaseModel

from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.knowledge import LimitGuide, StateGuide
from intelli_gateway.schemas.site_data import PointInfo
from intelli_gateway.schemas.tools import JSONValue
from intelli_gateway.tools.base import ToolError


@dataclass(frozen=True)
class SiteToolLimits:
    max_rows: int
    history_samples: int
    history_max_days: int
    max_text_chars: int


def site_id_of(ctx: RequestContext) -> int:
    if ctx.site_id is None:  # authz.check already rejects this; kept for the type checker
        raise ToolError("no site in request context")
    return ctx.site_id


def dump(model: BaseModel) -> dict[str, JSONValue]:
    """A model as JSON-ready data, without empty or default fields (fewer tokens)."""
    return model.model_dump(mode="json", exclude_none=True, exclude_defaults=True)


async def resolve_point(site_data: SiteDataConnector, site_id: int, name: str) -> PointInfo:
    for point in await site_data.list_points(site_id):
        if point.name == name:
            return point
    raise ToolError(f"point not found: {name}", hint="call list_points to see valid names")


def is_discrete(point: PointInfo) -> bool:
    """Status, alarm and fault-code points: integer codes whose history is a list of changes."""
    return bool(point.enum_labels or point.bit_labels) or point.data_type.startswith(
        ("enum", "bitfield", "status_word")
    )


def guidance_entry(point_name: str, entry: StateGuide | LimitGuide) -> dict[str, JSONValue]:
    """One applicable guide entry, as a tool returns it."""
    return {"point": point_name, **dump(entry)}
