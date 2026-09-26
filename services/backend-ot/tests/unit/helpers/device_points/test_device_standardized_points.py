"""
Unit tests for the standardized-points registry in helpers.device_points.

Guards the device-type vocabulary against the registry it feeds. The original bug:
'meter'/'RTAC' were accepted but matched no registry key (0 standardized points,
silently), while ES/PV/GENERATOR/LOADBANK/IED had templates the API rejected outright.
"""

from helpers.device_points.device_standardized_points import (
    _STANDARDIZED_POINTS,
    generate_standardized_points,
)
from schemas.api_models.types import SUPPORTED_DEVICE_TYPES


class TestStandardizedPointsRegistry:
    # Valid device types that intentionally have no standardized-point templates yet.
    NO_TEMPLATE_YET = {"METER", "RTAC"}

    def test_every_device_type_has_templates_or_is_explicitly_exempt(self):
        for device_type in SUPPORTED_DEVICE_TYPES:
            assert device_type in _STANDARDIZED_POINTS or device_type in self.NO_TEMPLATE_YET, (
                f"{device_type} is accepted but generates no standardized points. "
                f"Add templates, or add it to NO_TEMPLATE_YET deliberately."
            )

    def test_every_template_is_reachable(self):
        """A template whose key the API rejects can never be used."""
        for registry_key in _STANDARDIZED_POINTS:
            assert registry_key in SUPPORTED_DEVICE_TYPES, (
                f"{registry_key} has standardized points but is not an accepted device type."
            )

    def test_exempt_types_really_have_no_templates(self):
        """Keeps NO_TEMPLATE_YET honest once templates are added."""
        for device_type in self.NO_TEMPLATE_YET:
            assert device_type not in _STANDARDIZED_POINTS


class TestStandardizedPointClass:
    def test_status_and_position_points_are_binary_the_rest_analog(self):
        for definition in _STANDARDIZED_POINTS.values():
            for template in definition.points:
                is_state = template.name.endswith(("_STATUS", "_POSITION"))
                assert template.point_class == ("BINARY" if is_state else "ANALOG"), template.name

    def test_generated_points_carry_the_class_and_no_severity(self):
        points = generate_standardized_points("BESS", device_id=1, site_id=1001)
        assert {point.name: point.point_class for point in points} == {
            "BESS_ACTIVE_POWER": "ANALOG",
            "BESS_STATE_OF_CHARGE": "ANALOG",
            "BESS_STATUS": "BINARY",
        }
        assert all(point.severity is None for point in points)
