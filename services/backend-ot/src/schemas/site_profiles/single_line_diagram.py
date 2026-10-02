"""
A site's single line diagram (SLD): the electrical elements and how they connect, laid out
on a grid. A profile ships it as individual_sites/<key>/sld.json, validated against SiteSld
when the app starts, and GET /api/sites/{site_id}/sld serves it.

Coordinates are grid cells, not pixels: the UI picks the cell size. `col` grows to the
right and `row` grows downward (the utility side is usually row 0). Fractions are allowed,
e.g. col 1.5 to center a node between two others.
"""

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
