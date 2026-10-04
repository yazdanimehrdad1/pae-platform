"""`powerflow_server = yes` points: one powerflow point times a unit factor.

The powerflow point is relative to the device's asset (`p_kw` on BESS-1 reads `bess.bess1.p_kw`;
the site and POI meter read `poi.meter.*`).
"""

from powerflow.point_standard.layout import Device, DeviceKind
from powerflow.point_standard.sources import Resolver, Sources, powerflow_prefix

KILO = 1000.0  # kW → W, kvar → var, kVA → VA, kWh → Wh, kV → V

_METER: dict[str, tuple[str, float]] = {
    "A": ("i_a", 1.0),
    "PPV": ("v_kv", KILO),
    "W": ("p_kw", KILO),
    "VAR": ("q_kvar", KILO),
    "VA": ("s_kva", KILO),
    "PF": ("pf", 1.0),
}

DIRECT: dict[DeviceKind, dict[str, tuple[str, float]]] = {
    DeviceKind.SITE: {
        "SiteW": ("p_kw", KILO),
        "SiteVar": ("q_kvar", KILO),
        "SiteVA": ("s_kva", KILO),
        "SitePF": ("pf", 1.0),
        "SiteV": ("v_kv", KILO),
        "SiteVPu": ("v_pu", 1.0),
        "WLoss": ("p_loss_total_kw", KILO),
    },
    DeviceKind.BESS: {
        "W": ("p_kw", KILO),
        "Var": ("q_kvar", KILO),
        "VA": ("s_kva", KILO),
        "LLV": ("v_lv_kv", KILO),
        "SoC": ("soc_pct", 1.0),
        "WHRtg": ("capacity_kwh", KILO),
        "WChaRteMax": ("p_rated_charge_kw", KILO),
        "WDisChaRteMax": ("p_rated_discharge_kw", KILO),
        "SoCMax": ("soc_max_pct", 1.0),
        "SoCMin": ("soc_min_pct", 1.0),
        "WAvailDisCha": ("p_available_discharge_kw", KILO),
        "WAvailCha": ("p_available_charge_kw", KILO),
        "WHAvailDisCha": ("energy_available_discharge_kwh", KILO),
        "WHAvailCha": ("energy_available_charge_kwh", KILO),
        "AuxW": ("aux_p_kw", KILO),
        "WSet": ("p_setpoint_kw", KILO),
        "VarSet": ("q_setpoint_kvar", KILO),
        "WCmd": ("p_cmd_kw", KILO),
        "VarCmd": ("q_cmd_kvar", KILO),
        "WMaxRtg": ("p_rated_discharge_kw", KILO),
        "VAMaxRtg": ("s_rated_kva", KILO),
    },
    DeviceKind.PV: {
        "W": ("p_kw", KILO),
        "Var": ("q_kvar", KILO),
        "VA": ("s_kva", KILO),
        "PF": ("pf", 1.0),
        "LLV": ("v_lv_kv", KILO),
        "DCWRtg": ("dc_kwp", KILO),
        "WAvail": ("p_available_kw", KILO),
        "WCurt": ("curtailment_kw", KILO),
        "WMaxLimPct": ("p_limit_pct", 1.0),
        "WMaxLim": ("p_limit_kw", KILO),
        "VarSet": ("q_setpoint_kvar", KILO),
        "WMaxRtg": ("p_max_kw", KILO),
        "VAMaxRtg": ("s_rated_kva", KILO),
    },
    DeviceKind.LOAD: {
        "W": ("p_kw", KILO),
        "VAR": ("q_kvar", KILO),
        "VA": ("s_kva", KILO),
        "PF": ("pf", 1.0),
        "SupplySt": ("supply_state", 1.0),  # same codes as pae.SupplySt
        "Alrm": ("alarm_flags", 1.0),  # same bits as pae.LoadAlrm
    },
    DeviceKind.POI_METER: _METER,
    DeviceKind.FEEDER_METER: _METER,
}


def _direct(point: str, factor: float) -> Resolver:
    def resolve(sources: Sources, device: Device) -> float:
        return float(sources.read(f"{powerflow_prefix(device)}.{point}")) * factor

    return resolve


DIRECT_RESOLVERS: dict[DeviceKind, dict[str, Resolver]] = {
    kind: {point: _direct(source, factor) for point, (source, factor) in table.items()}
    for kind, table in DIRECT.items()
}
