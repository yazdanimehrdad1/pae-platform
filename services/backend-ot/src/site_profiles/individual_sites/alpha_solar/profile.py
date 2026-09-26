"""
Alpha Solar Farm (dev site 1001): the endpoints it offers.

Only what is declared here gets a URL. To add one: write the controller in functions.py
(or common/functions.py for a shared one), then declare a SiteEndpoint for it below.
"""

from schemas.site_profiles import EnergySummaryResult
from schemas.site_profiles.individual_sites.alpha_solar import (
    InverterAvailabilityResult,
    PoiPowerResult,
)
from site_profiles.common.functions import common_energy_summary
from site_profiles.individual_sites.alpha_solar.functions import (
    device_inverter_availability,
    device_plant_inverter_availability,
    site_poi_power,
)
from site_profiles.site_endpoint import SiteEndpoint, SiteProfile

ALPHA_SOLAR_PROFILE = SiteProfile(
    key="alpha_solar",
    endpoints=(
        SiteEndpoint(
            method="GET",
            kind="common",
            name="common-energy-summary",
            controller=common_energy_summary,
            response_model=EnergySummaryResult,
            summary="Energy (kWh) per device and in total, integrated from each device's active_power",
        ),
        SiteEndpoint(
            method="GET",
            kind="site",
            name="site-poi-power",
            controller=site_poi_power,
            response_model=PoiPowerResult,
            summary="Point-of-interconnection active power series, with peak and average (kW)",
        ),
        SiteEndpoint(
            method="GET",
            kind="device",
            name="device-inverter-availability",
            controller=device_inverter_availability,
            response_model=InverterAvailabilityResult,
            summary="Inverter availability (%): share of inverter_state samples in mppt or derating",
        ),
        SiteEndpoint(
            method="GET",
            kind="device",
            name="device-plant-inverter-availability",
            controller=device_plant_inverter_availability,
            response_model=InverterAvailabilityResult,
            summary="Plant inverter availability (%): pooled over the plant controller's inv01..04_mode",
        ),
    ),
)
