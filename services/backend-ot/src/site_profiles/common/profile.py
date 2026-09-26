"""
The built-in 'default' profile: every site starts here until it has its own profile.

It declares only common endpoints (it has no site code of its own). To give a site its
own endpoints, create site_profiles/individual_sites/<site>/profile.py and set the
site's profile to it.
"""

from schemas.site_profiles import EnergySummaryResult
from site_profiles.common.functions import common_energy_summary
from site_profiles.site_endpoint import SiteEndpoint, SiteProfile

DEFAULT_PROFILE_KEY = "default"

DEFAULT_PROFILE = SiteProfile(
    key=DEFAULT_PROFILE_KEY,
    endpoints=(
        SiteEndpoint(
            method="GET",
            kind="common",
            name="common-energy-summary",
            controller=common_energy_summary,
            response_model=EnergySummaryResult,
            summary="Energy (kWh) per device and in total, integrated from each device's active_power",
        ),
    ),
)
