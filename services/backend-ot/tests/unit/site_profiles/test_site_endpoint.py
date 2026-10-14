"""
Unit tests for site_profiles.declarations.endpoint.

Guards the standard endpoint declaration: a controller must be async, device_types is only
for device endpoints, and a profile
serves exactly the endpoints it declares, looked up by their full prefixed name.
"""

import pytest
from pydantic import BaseModel, ValidationError

from schemas.site_profiles import EnergySummaryResult, SiteContext, TimeWindowParams
from schemas.site_profiles.individual_sites.alpha_solar import InverterAvailabilityResult
from site_profiles.declarations.endpoint import SiteEndpoint
from site_profiles.individual_sites.alpha_solar.alpha_solar_functions import (
    device_inverter_availability,
    device_plant_inverter_availability,
    site_energy_series,
    site_energy_summary,
    site_poi_power,
)
from site_profiles.individual_sites.alpha_solar.profile import ALPHA_SOLAR_PROFILE


def sync_controller(ctx: SiteContext, params: TimeWindowParams) -> BaseModel:
    return BaseModel()


class TestSiteEndpoint:
    def test_sync_controller_is_rejected(self):
        with pytest.raises(ValidationError, match="async def"):
            SiteEndpoint(
                method="GET",
                kind="common",
                name="common-sync",
                controller=sync_controller,  # type: ignore[arg-type]
                response_model=BaseModel,
                summary="sync",
            )

    def test_params_model_defaults_to_time_window(self):
        endpoint = SiteEndpoint(
            method="GET",
            kind="site",
            name="site-energy-summary",
            controller=site_energy_summary,
            response_model=EnergySummaryResult,
            summary="energy",
        )
        assert endpoint.params_model is TimeWindowParams

    def test_output_defaults_to_scalar_for_every_device(self):
        endpoint = SiteEndpoint(
            method="GET",
            kind="site",
            name="site-energy-summary",
            controller=site_energy_summary,
            response_model=EnergySummaryResult,
            summary="energy",
        )
        assert endpoint.output == "scalar"
        assert endpoint.device_types == ()

    def test_device_endpoint_may_name_device_types(self):
        endpoint = SiteEndpoint(
            method="GET",
            kind="device",
            name="device-inverter-availability",
            controller=device_inverter_availability,
            response_model=InverterAvailabilityResult,
            summary="availability",
            device_types=("INVERTER", "PV"),
        )
        assert endpoint.device_types == ("INVERTER", "PV")

    @pytest.mark.parametrize("kind", ["site", "common"])
    def test_device_types_on_a_non_device_endpoint_is_rejected(self, kind):
        with pytest.raises(ValidationError, match="only for device endpoints"):
            SiteEndpoint(
                method="GET",
                kind=kind,
                name=f"{kind}-energy-summary",
                controller=site_energy_summary,
                response_model=EnergySummaryResult,
                summary="energy",
                device_types=("INVERTER",),
            )

    def test_unknown_device_type_is_rejected(self):
        with pytest.raises(ValidationError):
            SiteEndpoint(
                method="GET",
                kind="device",
                name="device-inverter-availability",
                controller=device_inverter_availability,
                response_model=InverterAvailabilityResult,
                summary="availability",
                device_types=("TOASTER",),  # type: ignore[arg-type]
            )

    def test_only_get_is_allowed(self):
        with pytest.raises(ValidationError):
            SiteEndpoint(
                method="POST",  # type: ignore[arg-type]
                kind="site",
                name="site-energy-summary",
                controller=site_energy_summary,
                response_model=EnergySummaryResult,
                summary="energy",
            )


class TestFindEndpoint:
    def test_finds_each_declared_endpoint_by_name(self):
        controllers = {
            "site-energy-series": site_energy_series,
            "site-energy-summary": site_energy_summary,
            "site-poi-power": site_poi_power,
            "device-inverter-availability": device_inverter_availability,
            "device-plant-inverter-availability": device_plant_inverter_availability,
        }
        for name, controller in controllers.items():
            endpoint = ALPHA_SOLAR_PROFILE.find_endpoint(name)
            assert endpoint is not None
            assert endpoint.controller is controller

    def test_undeclared_endpoint_is_none(self):
        assert ALPHA_SOLAR_PROFILE.find_endpoint("site-no-such-endpoint") is None

    def test_name_without_prefix_is_none(self):
        assert ALPHA_SOLAR_PROFILE.find_endpoint("energy-summary") is None
