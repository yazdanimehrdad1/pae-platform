"""
A site's single line diagram (SLD): the electrical elements and how they connect, laid out
on a grid. Stored per site in the site_slds table (one JSONB document, validated against
SiteSld on every write) and served by /api/sites/{site_id}/sld.

Coordinates are grid cells, not pixels: the UI picks the cell size. `col` grows to the
right and `row` grows downward (the utility side is usually row 0). Fractions are allowed,
e.g. col 1.5 to center a node between two others.
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SldNodeType = Literal[
    "grid",
    "poi",
    "meter",
    "transformer",
    "breaker",
    "switch",
    "pv",
    "inverter",
    "bess",
    "generator",
    "wind",
    "load",
    "plant_controller",
]

_ID_PATTERN = r"^[a-z0-9]+([_-][a-z0-9]+)*$"

# A value an element's info box shows, read from one point of its linked device.
SldRole = Literal["vab", "vbc", "vca", "ia", "ib", "ic", "in", "soc", "power", "mode", "irradiance"]

# The roles each linkable element type shows, in display order. Only these types take a device.
SLD_ROLES_BY_NODE_TYPE: dict[SldNodeType, tuple[SldRole, ...]] = {
    "meter": ("vab", "vbc", "vca", "ia", "ib", "ic", "in"),
    "bess": ("soc", "power", "mode"),
    "pv": ("power", "irradiance"),
}


class SldDeviceLink(BaseModel):
    """The backend device an element shows values of, and which of its points fills each role."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    device_id: int = Field(..., description="A device of this site")
    points: dict[SldRole, int] = Field(
        default_factory=dict,
        description="Role -> point id of that device. An unmapped role shows as not available",
    )


class SldNode(BaseModel):
    """One element of the diagram, drawn as a box centered on its grid cell."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        ..., pattern=_ID_PATTERN, description="Unique within the diagram (nodes and buses)"
    )
    type: SldNodeType = Field(..., description="What the element is; picks its icon")
    name: str = Field(..., min_length=1, description="Label shown on the element")
    voltage: str | None = Field(None, description="Nominal voltage label, e.g. '34.5 kV'")
    rating: str | None = Field(None, description="Rating label, e.g. '5 MVA' or '2 MW / 4 MWh'")
    col: float = Field(..., description="Grid column of the element's center")
    row: float = Field(..., description="Grid row of the element's center")
    device: SldDeviceLink | None = Field(
        None,
        description="Linked device for the element's info box; only meter, bess and pv elements take one",
    )

    @model_validator(mode="after")
    def _check_device_roles(self) -> Self:
        if self.device is None:
            return self
        allowed = SLD_ROLES_BY_NODE_TYPE.get(self.type)
        if allowed is None:
            raise ValueError(
                f"node '{self.id}': a {self.type} element takes no device; "
                f"only {', '.join(SLD_ROLES_BY_NODE_TYPE)} do"
            )
        unknown = sorted(set(self.device.points) - set(allowed))
        if unknown:
            raise ValueError(
                f"node '{self.id}': role(s) {', '.join(unknown)} don't apply to a {self.type}; "
                f"its roles are {', '.join(allowed)}"
            )
        return self


class SldBus(BaseModel):
    """A horizontal bus bar on one row, spanning col_start..col_end."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        ..., pattern=_ID_PATTERN, description="Unique within the diagram (nodes and buses)"
    )
    name: str = Field(..., min_length=1, description="Label shown on the bus")
    voltage: str | None = Field(None, description="Nominal voltage label, e.g. '34.5 kV'")
    row: float = Field(..., description="Grid row of the bus")
    col_start: float = Field(..., description="Grid column of the bus's left end")
    col_end: float = Field(
        ..., description="Grid column of the bus's right end; greater than col_start"
    )


class SldConnection(BaseModel):
    """A conductor between two elements (node or bus), by id."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_id: str = Field(..., description="Id of a node or bus")
    to_id: str = Field(..., description="Id of a node or bus")


class SiteSld(BaseModel):
    """A site's single line diagram."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = Field(..., description="Version of this format")
    nodes: tuple[SldNode, ...] = Field(..., min_length=1)
    buses: tuple[SldBus, ...] = ()
    connections: tuple[SldConnection, ...] = ()

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        """Ids unique, connections between known distinct elements, buses non-empty, no stacked nodes."""
        ids: set[str] = set()
        for element_id in [node.id for node in self.nodes] + [bus.id for bus in self.buses]:
            if element_id in ids:
                raise ValueError(f"id '{element_id}' is used more than once")
            ids.add(element_id)

        for bus in self.buses:
            if bus.col_end <= bus.col_start:
                raise ValueError(f"bus '{bus.id}': col_end must be greater than col_start")

        cells: dict[tuple[float, float], str] = {}
        for node in self.nodes:
            other = cells.setdefault((node.col, node.row), node.id)
            if other != node.id:
                raise ValueError(
                    f"nodes '{other}' and '{node.id}' are on the same cell ({node.col}, {node.row})"
                )

        pairs: set[frozenset[str]] = set()
        for connection in self.connections:
            for end in (connection.from_id, connection.to_id):
                if end not in ids:
                    raise ValueError(
                        f"connection {connection.from_id} -> {connection.to_id}: unknown id '{end}'"
                    )
            if connection.from_id == connection.to_id:
                raise ValueError(
                    f"connection {connection.from_id} -> {connection.to_id} connects an element to itself"
                )
            pair = frozenset((connection.from_id, connection.to_id))
            if pair in pairs:
                raise ValueError(
                    f"connection {connection.from_id} -> {connection.to_id} is declared twice"
                )
            pairs.add(pair)
        return self


# --- Live values for the info boxes (GET /api/sites/{site_id}/sld/values) ----------------


class DeviceHealth(BaseModel):
    """A device's health verdict: healthy, unhealthy, or unknown (None, shown as not available).
    Decided by the site profile's device health checks."""

    healthy: bool | None = Field(..., description="None when it can't be judged, e.g. no readings yet")
    reason: str | None = Field(None, description="Why it is unhealthy or unknown, for a tooltip")


class SldValue(BaseModel):
    """The latest reading of the point filling one role."""

    point_id: int
    value: float | None = Field(None, description="Scaled value, in `unit`; None if never read")
    label: str | None = Field(None, description="The enum label for an enum point, e.g. 'discharging'")
    unit: str | None = Field(None, description="Unit of `value`; power roles are converted to kW")
    time: datetime | None = Field(None, description="When it was read; None if never read")


class SldNodeValues(BaseModel):
    """One linked element's info box: a value per role, in display order, and the device health."""

    node_id: str
    device_id: int
    values: dict[SldRole, SldValue | None] = Field(
        ..., description="Every role of the element's type, in display order; null = not available"
    )
    health: DeviceHealth | None = Field(
        None, description="Only for element types that show health (bess, pv); null if the site declares no check"
    )


class SldValuesResponse(BaseModel):
    """The live values of every SLD element linked to a device."""

    site_id: int
    sld_revision: int = Field(..., description="The SLD revision these links come from")
    generated_at: datetime
    nodes: list[SldNodeValues]
