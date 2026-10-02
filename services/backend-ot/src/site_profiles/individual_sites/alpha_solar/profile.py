"""
Alpha Solar Farm (dev site 1001): the endpoints and alarms it offers.

Only what is declared here gets a URL (endpoints) or an alarm row per site (alarms). To add one: write the controller in functions.py
(or common/functions.py for a shared one), then declare a SiteEndpoint for it below.
Its single line diagram is sld.json in this folder (format: schemas/site_profiles/single_line_diagram.py).
"""

from pathlib import Path

from schemas.site_profiles import EnergySummaryResult
from schemas.site_profiles.individual_sites.alpha_solar import (
    InverterAvailabilityResult,
    PoiPowerResult,
)
from site_profiles.common.functions import common_energy_summary
from site_profiles.individual_sites.alpha_solar.alarms import placeholder_profile_alarm_1
from site_profiles.individual_sites.alpha_solar.functions import (
    device_inverter_availability,
    device_plant_inverter_availability,
    site_poi_power,
)
from site_profiles.site_alarm import SiteAlarm
from site_profiles.site_endpoint import SiteEndpoint, SiteProfile
from site_profiles.site_sld import load_site_sld

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
    alarms=(
        # PLACEHOLDER: an example of a profile alarm, not a real alarm of the site.
        SiteAlarm(
            key="placeholder_profile_alarm_1",
            name="placeholder_profile_alarm_1",
            severity="fault",
            message="PLACEHOLDER profile alarm 1: inverter_state is not mppt or derating",
            evaluate=placeholder_profile_alarm_1,
        ),
    ),
    # DRAFT topology built from the mock devices; replace with the site's real SLD.
    sld=load_site_sld(Path(__file__).parent / "sld.json"),
)
