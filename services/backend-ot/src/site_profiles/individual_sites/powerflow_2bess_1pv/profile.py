"""
Powerflow 2BESS 1PV (powerflow's simulated 2bess_1pv site): the endpoints it offers.

Only what is declared here gets a URL (endpoints) or a stored VIRTUAL point (virtual_points). To add
one: declare its SPF points in powerflow_2bess_1pv_points.py, write its code in
powerflow_2bess_1pv_functions.py, then declare it below.

Its functions are computed on request; nothing is stored. To store one in a VIRTUAL point instead,
give it a compute function (async (VirtualPointContext) -> list[TimestampedValue]) that calls
spf_common_sum_points with the same SPF points, and declare it under virtual_points=(...) here
(see site_profiles/common/spf_point_functions.py).
"""

from schemas.site_profiles.individual_sites.powerflow_2bess_1pv import (
    BessRollingRoundTripEfficiencyResult,
    BessRoundTripEfficiencyResult,
    PowerSeriesResult,
    RollingRoundTripEfficiencyParams,
)
from site_profiles.declarations.endpoint import SiteEndpoint
from site_profiles.declarations.profile import SiteProfile
from site_profiles.individual_sites.powerflow_2bess_1pv.powerflow_2bess_1pv_functions import (
    site_assets_active_power,
    site_assets_reactive_power,
    site_bess1_rolling_round_trip_efficiency,
    site_bess1_round_trip_efficiency,
    site_bess2_rolling_round_trip_efficiency,
    site_bess2_round_trip_efficiency,
    site_poi_active_power,
    site_poi_reactive_power,
)

POWERFLOW_2BESS_1PV_PROFILE = SiteProfile(
    key="powerflow_2bess_1pv",
    endpoints=(
        SiteEndpoint(
            method="GET",
            kind="site",
            name="site-poi-active-power",
            controller=site_poi_active_power,
            response_model=PowerSeriesResult,
            summary="The POI meter's active power series (kW), with peak and average",
            output="series",
        ),
        SiteEndpoint(
            method="GET",
            kind="site",
            name="site-poi-reactive-power",
            controller=site_poi_reactive_power,
            response_model=PowerSeriesResult,
            summary="The POI meter's reactive power series (kvar), with peak and average",
            output="series",
        ),
        SiteEndpoint(
            method="GET",
            kind="site",
            name="site-assets-active-power",
            controller=site_assets_active_power,
            response_model=PowerSeriesResult,
            summary="BESS 1 + BESS 2 + PV 1 active power series (kW), with peak and average",
            output="series",
        ),
        SiteEndpoint(
            method="GET",
            kind="site",
            name="site-assets-reactive-power",
            controller=site_assets_reactive_power,
            response_model=PowerSeriesResult,
            summary="BESS 1 + BESS 2 + PV 1 reactive power series (kvar), with peak and average",
            output="series",
        ),
        SiteEndpoint(
            method="GET",
            kind="site",
            name="site-bess1-round-trip-efficiency",
            controller=site_bess1_round_trip_efficiency,
            response_model=BessRoundTripEfficiencyResult,
            summary="BESS 1's round trip efficiency (%), corrected for its change in SoC",
        ),
        SiteEndpoint(
            method="GET",
            kind="site",
            name="site-bess2-round-trip-efficiency",
            controller=site_bess2_round_trip_efficiency,
            response_model=BessRoundTripEfficiencyResult,
            summary="BESS 2's round trip efficiency (%), corrected for its change in SoC",
        ),
        SiteEndpoint(
            method="GET",
            kind="site",
            name="site-bess1-rolling-round-trip-efficiency",
            controller=site_bess1_rolling_round_trip_efficiency,
            params_model=RollingRoundTripEfficiencyParams,
            response_model=BessRollingRoundTripEfficiencyResult,
            summary="BESS 1's round trip efficiency (%) over time, each value over the last lookback_days",
            output="series",
        ),
        SiteEndpoint(
            method="GET",
            kind="site",
            name="site-bess2-rolling-round-trip-efficiency",
            controller=site_bess2_rolling_round_trip_efficiency,
            params_model=RollingRoundTripEfficiencyParams,
            response_model=BessRollingRoundTripEfficiencyResult,
            summary="BESS 2's round trip efficiency (%) over time, each value over the last lookback_days",
            output="series",
        ),
    ),
)
