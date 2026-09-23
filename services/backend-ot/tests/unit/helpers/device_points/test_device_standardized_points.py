"""
Unit tests for the standardized-points registry in helpers.device_points.

Guards the device-type vocabulary against the registry it feeds. The original bug:
'meter'/'RTAC' were accepted but matched no registry key (0 standardized points,
silently), while ES/PV/GENERATOR/LOADBANK/IED had templates the API rejected outright.
"""

from helpers.device_points.device_standardized_points import _STANDARDIZED_POINTS
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
