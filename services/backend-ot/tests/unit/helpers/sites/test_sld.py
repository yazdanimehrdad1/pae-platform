"""
Unit tests for helpers.sites.sld.

Guards the SLD device links against the site's real devices (a foreign device or a point of
another device is reported, valid links pass), and how readings become info-box values: every
role of the element's type in display order, power in kW, enum labels, and not-available (None)
for an unmapped role or a missing point.
"""

from helpers.sites.sld import node_role_values, sld_link_errors, sld_value
from schemas.api_models import SiteSld, SldDeviceLink, SldNode
from unit.site_fixtures import make_device, make_point, make_reading

BATTERY_STATES = {"0": "standby", "1": "charging", "2": "discharging"}


def bess_node(points: dict, device_id: int = 2) -> SldNode:
    return SldNode(id="bess", type="bess", name="BESS", col=0, row=0, device=SldDeviceLink(device_id=device_id, points=points))


def sld_with(node: SldNode) -> SiteSld:
    return SiteSld(schema_version=1, nodes=(node,))


class TestSldLinkErrors:
    devices = [make_device(2, [make_point(20, 2, "state_of_charge")]), make_device(3, [make_point(30, 3, "poi_current_a")])]

    def test_valid_links_have_no_errors(self):
        assert sld_link_errors(sld_with(bess_node({"soc": 20})), self.devices) == []

    def test_unlinked_nodes_are_ignored(self):
        assert sld_link_errors(SiteSld(schema_version=1, nodes=(SldNode(id="g", type="grid", name="G", col=0, row=0),)), []) == []

    def test_unknown_device_is_reported(self):
        (error,) = sld_link_errors(sld_with(bess_node({"soc": 20}, device_id=9)), self.devices)
        assert "device 9 is not a device of this site" in error

    def test_point_of_another_device_is_reported(self):
        (error,) = sld_link_errors(sld_with(bess_node({"soc": 30})), self.devices)
        assert "soc point 30 is not a point of device 2" in error


class TestSldValue:
    def test_power_in_watts_is_converted_to_kw(self):
        value = sld_value("power", make_reading(1, 4200.0, unit="W"))
        assert (value.value, value.unit) == (4.2, "kW")

    def test_power_in_mw_is_converted_to_kw(self):
        value = sld_value("power", make_reading(1, 1.5, unit="MW"))
        assert (value.value, value.unit) == (1500.0, "kW")

    def test_power_with_unknown_unit_is_left_as_is(self):
        value = sld_value("power", make_reading(1, 7.0, unit=None))
        assert (value.value, value.unit) == (7.0, None)

    def test_non_power_roles_keep_their_unit(self):
        value = sld_value("ia", make_reading(1, 812.0, unit="A"))
        assert (value.value, value.unit) == (812.0, "A")

    def test_enum_gets_its_label(self):
        value = sld_value("mode", make_reading(1, 2.0, enum_detail=BATTERY_STATES))
        assert value.label == "discharging"

    def test_never_read_point_has_no_value_or_label(self):
        value = sld_value("mode", make_reading(1, None, enum_detail=BATTERY_STATES))
        assert (value.value, value.label, value.time) == (None, None, None)


class TestNodeRoleValues:
    def test_every_role_of_the_type_in_display_order(self):
        values = node_role_values(bess_node({"soc": 20}), {20: make_reading(20, 68.0, unit="%")})
        assert list(values) == ["soc", "power", "mode"]
        assert values["soc"] is not None and values["soc"].value == 68.0

    def test_unmapped_role_is_none(self):
        values = node_role_values(bess_node({"soc": 20}), {20: make_reading(20, 68.0)})
        assert values["power"] is None and values["mode"] is None

    def test_mapped_point_without_reading_is_none(self):
        # e.g. the point was deleted, so the controller didn't read it
        assert node_role_values(bess_node({"soc": 20}), {})["soc"] is None

    def test_meter_lists_its_seven_roles(self):
        meter = SldNode(id="m", type="meter", name="M", col=0, row=0, device=SldDeviceLink(device_id=3, points={}))
        assert list(node_role_values(meter, {})) == ["vab", "vbc", "vca", "ia", "ib", "ic", "in"]
