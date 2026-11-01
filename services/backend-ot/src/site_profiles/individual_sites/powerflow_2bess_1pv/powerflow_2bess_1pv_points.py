"""
The SPF points the Powerflow 2BESS 1PV site's functions read (site_profiles/declarations/spf_point.py).

Devices are named as the powerflow seed names them ('2bess_1pv-<asset>'). Their power points are
stored in kW / kvar already (scale 1), and every one reads export positive (sign +1): a charging
BESS and an importing POI are negative.
"""

from site_profiles.declarations.spf_point import SpfPoint

SPF_POI_ACTIVE_POWER = SpfPoint(
    device="2bess_1pv-poi_meter",
    point="METER_ACTIVE_POWER",
    category="STANDARDIZED",
    scale=1.0,
    sign=1,
)
SPF_POI_REACTIVE_POWER = SpfPoint(
    device="2bess_1pv-poi_meter",
    point="METER_REACTIVE_POWER",
    category="STANDARDIZED",
    scale=1.0,
    sign=1,
)

SPF_BESS1_ACTIVE_POWER = SpfPoint(
    device="2bess_1pv-bess1", point="BESS_ACTIVE_POWER", category="STANDARDIZED", scale=1.0, sign=1
)
SPF_BESS2_ACTIVE_POWER = SpfPoint(
    device="2bess_1pv-bess2", point="BESS_ACTIVE_POWER", category="STANDARDIZED", scale=1.0, sign=1
)
SPF_PV1_ACTIVE_POWER = SpfPoint(
    device="2bess_1pv-pv1", point="PV_ACTIVE_POWER", category="STANDARDIZED", scale=1.0, sign=1
)

# BESS and PV have no STANDARDIZED reactive power point: their NATIVE 'Var' register.
SPF_BESS1_REACTIVE_POWER = SpfPoint(
    device="2bess_1pv-bess1", point="Var", category="NATIVE", scale=1.0, sign=1
)
SPF_BESS2_REACTIVE_POWER = SpfPoint(
    device="2bess_1pv-bess2", point="Var", category="NATIVE", scale=1.0, sign=1
)
SPF_PV1_REACTIVE_POWER = SpfPoint(
    device="2bess_1pv-pv1", point="Var", category="NATIVE", scale=1.0, sign=1
)

SPF_BESS1_STATE_OF_CHARGE = SpfPoint(
    device="2bess_1pv-bess1",
    point="BESS_STATE_OF_CHARGE",
    category="STANDARDIZED",
    scale=1.0,
    sign=1,
)
SPF_BESS2_STATE_OF_CHARGE = SpfPoint(
    device="2bess_1pv-bess2",
    point="BESS_STATE_OF_CHARGE",
    category="STANDARDIZED",
    scale=1.0,
    sign=1,
)

# The points each site function sums.
SITE_POI_ACTIVE_POWER = (SPF_POI_ACTIVE_POWER,)
SITE_POI_REACTIVE_POWER = (SPF_POI_REACTIVE_POWER,)
SITE_ASSETS_ACTIVE_POWER = (SPF_BESS1_ACTIVE_POWER, SPF_BESS2_ACTIVE_POWER, SPF_PV1_ACTIVE_POWER)
SITE_ASSETS_REACTIVE_POWER = (
    SPF_BESS1_REACTIVE_POWER,
    SPF_BESS2_REACTIVE_POWER,
    SPF_PV1_REACTIVE_POWER,
)
