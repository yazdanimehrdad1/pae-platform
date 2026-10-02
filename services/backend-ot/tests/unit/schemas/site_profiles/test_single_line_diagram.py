"""
Unit tests for schemas.site_profiles.single_line_diagram.

Guards what makes a single line diagram drawable: ids are unique across nodes and buses,
every connection joins two distinct known elements once, a bus spans left to right, no two
nodes sit on the same cell, and unknown fields or versions are rejected.
"""

import pytest
from pydantic import ValidationError

from schemas.site_profiles import SiteSld, SldBus, SldConnection, SldNode

GRID = SldNode(id="utility", type="grid", name="Utility", col=0, row=0)
BUS = SldBus(id="mv_bus", name="MV Bus", row=1, col_start=-1, col_end=1)
PV = SldNode(id="pv_1", type="pv", name="PV 1", col=0, row=2)


def build_sld(
    nodes: tuple[SldNode, ...] = (GRID, PV),
    buses: tuple[SldBus, ...] = (BUS,),
    connections: tuple[SldConnection, ...] = (
        SldConnection(from_id="utility", to_id="mv_bus"),
        SldConnection(from_id="mv_bus", to_id="pv_1"),
    ),
) -> SiteSld:
    return SiteSld(schema_version=1, nodes=nodes, buses=buses, connections=connections)


class TestValidSld:
    def test_minimal_sld_validates(self):
        sld = build_sld()
        assert [node.id for node in sld.nodes] == ["utility", "pv_1"]
        assert sld.buses[0].col_end == 1

    def test_buses_and_connections_are_optional(self):
        sld = SiteSld(schema_version=1, nodes=(GRID,))
        assert sld.buses == ()
        assert sld.connections == ()

    def test_round_trips_through_json(self):
        sld = build_sld()
        assert SiteSld.model_validate_json(sld.model_dump_json()) == sld


class TestRejectedSld:
    def test_no_nodes_is_rejected(self):
        with pytest.raises(ValidationError):
            SiteSld(schema_version=1, nodes=())

    def test_duplicate_node_id_is_rejected(self):
        twin = PV.model_copy(update={"col": 5})
        with pytest.raises(ValidationError, match="'pv_1' is used more than once"):
            build_sld(nodes=(GRID, PV, twin), connections=())

    def test_bus_sharing_a_node_id_is_rejected(self):
        bus = BUS.model_copy(update={"id": "pv_1"})
        with pytest.raises(ValidationError, match="'pv_1' is used more than once"):
            build_sld(buses=(bus,), connections=())

    def test_connection_to_unknown_id_is_rejected(self):
        with pytest.raises(ValidationError, match="unknown id 'ghost'"):
            build_sld(connections=(SldConnection(from_id="mv_bus", to_id="ghost"),))

    def test_self_loop_is_rejected(self):
        with pytest.raises(ValidationError, match="connects an element to itself"):
            build_sld(connections=(SldConnection(from_id="pv_1", to_id="pv_1"),))

    def test_duplicate_connection_is_rejected_in_either_direction(self):
        with pytest.raises(ValidationError, match="declared twice"):
            build_sld(
                connections=(
                    SldConnection(from_id="mv_bus", to_id="pv_1"),
                    SldConnection(from_id="pv_1", to_id="mv_bus"),
                )
            )

    @pytest.mark.parametrize("col_end", [-1, -2])
    def test_bus_not_spanning_left_to_right_is_rejected(self, col_end: float):
        bus = BUS.model_copy(update={"col_end": col_end})
        with pytest.raises(ValidationError, match="col_end must be greater than col_start"):
            build_sld(buses=(bus,))

    def test_two_nodes_on_one_cell_are_rejected(self):
        stacked = SldNode(id="pv_2", type="pv", name="PV 2", col=0, row=2)
        with pytest.raises(ValidationError, match="same cell"):
            build_sld(nodes=(GRID, PV, stacked), connections=())

    def test_unknown_node_type_is_rejected(self):
        raw = GRID.model_dump() | {"type": "flux_capacitor"}
        with pytest.raises(ValidationError):
            SldNode.model_validate(raw)

    def test_unknown_field_is_rejected(self):
        raw = GRID.model_dump() | {"colour": "red"}
        with pytest.raises(ValidationError):
            SldNode.model_validate(raw)

    def test_bad_id_is_rejected(self):
        raw = GRID.model_dump() | {"id": "Has Spaces"}
        with pytest.raises(ValidationError):
            SldNode.model_validate(raw)

    def test_unknown_schema_version_is_rejected(self):
        raw = build_sld().model_dump() | {"schema_version": 2}
        with pytest.raises(ValidationError):
            SiteSld.model_validate(raw)
