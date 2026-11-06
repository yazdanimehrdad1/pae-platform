"""
Powerflow 2BESS 1PV (powerflow's simulated 2bess_1pv site): the endpoints and alarms it offers.

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
from site_profiles.declarations.alarm import SiteAlarm
from site_profiles.declarations.endpoint import SiteEndpoint
from site_profiles.declarations.profile import SiteProfile
from site_profiles.individual_sites.powerflow_2bess_1pv.powerflow_2bess_1pv_alarms import (
    bess1_derated,
    bess1_fault,
    bess2_derated,
    bess2_fault,
    bess_soc_high,
    bess_soc_low,
    device_comm_loss,
    poi_frequency_critical,
    poi_problem,
    poi_voltage_critical,
    poi_voltage_out_of_range,
    pv1_derated,
    pv1_fault,
    pv_underperformance,
    transformer_overload,
)
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
    # 15 of the site's 20 enabled alarms, leaving 5 for user rules. Checks and thresholds:
    # powerflow_2bess_1pv_alarms.py.
    alarms=(
        # HIGH: act now.
        SiteAlarm(
            key="bess1_fault",
            name="bess1_fault",
            severity="HIGH",
            message="BESS 1 is faulted or its breaker is open",
            evaluate=bess1_fault,
        ),
        SiteAlarm(
            key="bess2_fault",
            name="bess2_fault",
            severity="HIGH",
            message="BESS 2 is faulted or its breaker is open",
            evaluate=bess2_fault,
        ),
        SiteAlarm(
            key="pv1_fault",
            name="pv1_fault",
            severity="HIGH",
            message="PV 1 is faulted or its breaker is open",
            evaluate=pv1_fault,
        ),
        SiteAlarm(
            key="poi_problem",
            name="poi_problem",
            severity="HIGH",
            message="The grid is lost at the POI (not grid-tied) or the POI meter failed",
            evaluate=poi_problem,
            clear_delay_sec=30,
        ),
        SiteAlarm(
            key="device_comm_loss",
            name="device_comm_loss",
            severity="HIGH",
            message="A device stopped communicating (plant controller or historian lost it)",
            evaluate=device_comm_loss,
            clear_delay_sec=30,
        ),
        SiteAlarm(
            key="poi_voltage_critical",
            name="poi_voltage_critical",
            severity="HIGH",
            message="POI voltage is more than 10 % from 12.47 kV",
            evaluate=poi_voltage_critical,
            delay_sec=10,
            clear_delay_sec=30,
        ),
        SiteAlarm(
            key="poi_frequency_critical",
            name="poi_frequency_critical",
            severity="HIGH",
            message="POI frequency is outside 59.3-60.5 Hz",
            evaluate=poi_frequency_critical,
            delay_sec=10,
            clear_delay_sec=30,
        ),
        # MEDIUM: look at it soon.
        SiteAlarm(
            key="bess1_derated",
            name="bess1_derated",
            severity="MEDIUM",
            message="BESS 1 reports a warning (over-temperature, fan, imbalance...) and may be derated",
            evaluate=bess1_derated,
            delay_sec=60,
            clear_delay_sec=60,
        ),
        SiteAlarm(
            key="bess2_derated",
            name="bess2_derated",
            severity="MEDIUM",
            message="BESS 2 reports a warning (over-temperature, fan, imbalance...) and may be derated",
            evaluate=bess2_derated,
            delay_sec=60,
            clear_delay_sec=60,
        ),
        SiteAlarm(
            key="pv1_derated",
            name="pv1_derated",
            severity="MEDIUM",
            message="PV 1 runs derated (blown string fuse, over-temperature or derating)",
            evaluate=pv1_derated,
            delay_sec=60,
            clear_delay_sec=60,
        ),
        SiteAlarm(
            key="poi_voltage_out_of_range",
            name="poi_voltage_out_of_range",
            severity="MEDIUM",
            message="POI voltage is outside ANSI C84.1 Range A (more than 5 % from 12.47 kV)",
            evaluate=poi_voltage_out_of_range,
            delay_sec=60,
            clear_delay_sec=60,
        ),
        SiteAlarm(
            key="transformer_overload",
            name="transformer_overload",
            severity="MEDIUM",
            message="An asset transformer is loaded above its kVA rating",
            evaluate=transformer_overload,
            delay_sec=60,
            clear_delay_sec=60,
        ),
        # LOW: worth knowing.
        SiteAlarm(
            key="bess_soc_low",
            name="bess_soc_low",
            severity="LOW",
            message="A BESS state of charge is below 10 %",
            evaluate=bess_soc_low,
            delay_sec=300,
            clear_delay_sec=300,
        ),
        SiteAlarm(
            key="bess_soc_high",
            name="bess_soc_high",
            severity="LOW",
            message="A BESS state of charge is above 90 %",
            evaluate=bess_soc_high,
            delay_sec=300,
            clear_delay_sec=300,
        ),
        SiteAlarm(
            key="pv_underperformance",
            name="pv_underperformance",
            severity="LOW",
            message="PV 1 produces less than 80 % of its available power while not curtailed",
            evaluate=pv_underperformance,
            delay_sec=900,
            clear_delay_sec=300,
        ),
    ),
)
