"""`powerflow_server = calc` points: values derived from the simulation results.

- **Balanced network:** the solver is positive-sequence, so every phase carries the same
  current and a third of the power, L-L voltages are equal, L-N = L-L/√3, and unbalance is 0.
- **Currents:** I = S/(√3·V_LL) (kVA/kV = A).
- **States and alarms:** powerflow's own status/flag codes, translated to the SunSpec/PAE codes
  in enums.csv by symbol name, so the numbers come from the standard.
- **Energy:** lifetime and daily counters from `EnergyCounters`.
- **Site:** fleet sums over the BESS and PV assets.
- **Frequency:** not simulated; a time-bucketed random signal around 60 Hz
  (`random_signal.GRID_HZ`), the same for every device.
"""

import math
from collections.abc import Callable, Sequence
from typing import Protocol, TypeVar

from powerflow.core.snapshot import (
    BessMeasurement,
    LoadMeasurement,
    MeterMeasurement,
    PoiMeasurement,
    PvMeasurement,
)
from powerflow.models import status
from powerflow.models.bess import BessFlag, BessStatus
from powerflow.models.common import power_factor
from powerflow.models.pv import PvFlag, PvQMode, PvStatus
from powerflow.models.status import (
    BessAlarm,
    BessOperatingState,
    MeterAlarm,
    MeterState,
    PvAlarm,
    PvInverterState,
)
from powerflow.point_standard.layout import Device, DeviceKind
from powerflow.point_standard.random_signal import GRID_HZ
from powerflow.point_standard.sources import Resolver, Sources, powerflow_prefix
from powerflow.site_config import PvAvailabilitySource

SQRT3 = math.sqrt(3.0)
KILO = 1000.0
MODE_PQ, MODE_OFFLINE = 1, 2  # BESS mode_cmd codes (powerflow.models.bess.BESS_MODE_CODES)
STATE_MARGIN_PCT = 0.01  # SoC this close to a limit counts as FULL / EMPTY


class _HasId(Protocol):
    @property
    def id(self) -> str: ...


ItemT = TypeVar("ItemT", bound=_HasId)


def _find(items: Sequence[ItemT], device: Device) -> ItemT:
    return next(item for item in items if item.id == device.asset_id)


def _bess(sources: Sources, device: Device) -> BessMeasurement:
    return _find(sources.snapshot.bess, device)


def _pv(sources: Sources, device: Device) -> PvMeasurement:
    return _find(sources.snapshot.pv, device)


def _load(sources: Sources, device: Device) -> LoadMeasurement:
    return _find(sources.snapshot.loads, device)


def _meter(sources: Sources, device: Device) -> PoiMeasurement | MeterMeasurement:
    if device.kind is DeviceKind.POI_METER:
        return sources.snapshot.poi
    return _find(sources.snapshot.meters, device)


def _current_a(s_kva: float, v_kv: float) -> float:
    return s_kva / (SQRT3 * v_kv) if v_kv > 0 else 0.0


def _map_bits(sources: Sources, flags: int, enum_ref: str, mapping: dict[int, str | None]) -> int:
    """Translate powerflow flag bits to bits of a standard bitfield (None = no equivalent)."""
    value = 0
    for flag, symbol in mapping.items():
        if flags & flag and symbol is not None:
            value |= sources.enums.bits(enum_ref, symbol)
    return value


def _setpoint(sources: Sources, device: Device, point: str) -> float:
    return float(sources.read(f"{powerflow_prefix(device)}.{point}"))


def _ena(sources: Sources, enabled: bool) -> int:
    return sources.enums.code("704.Ena", "ENABLED" if enabled else "DISABLED")


# -- shared ------------------------------------------------------------------------------------


def _per_phase_ac(
    measurement: Callable[[Sources, Device], tuple[float, float]],
) -> dict[str, Resolver]:
    """Phase currents and voltages of a DER from (S kVA, V_LL kV)."""

    def current(sources: Sources, device: Device) -> float:
        return _current_a(*measurement(sources, device))

    def v_ll(sources: Sources, device: Device) -> float:
        return measurement(sources, device)[1] * KILO

    def v_ln(sources: Sources, device: Device) -> float:
        return v_ll(sources, device) / SQRT3

    return {
        "A": current,
        "AL1": current,
        "AL2": current,
        "AL3": current,
        "VL1L2": v_ll,
        "VL2L3": v_ll,
        "VL3L1": v_ll,
        "LNV": v_ln,
        "VL1": v_ln,
        "VL2": v_ln,
        "VL3": v_ln,
    }


def _ac_type(sources: Sources, _device: Device) -> int:
    return sources.enums.code("701.ACType", "THREE_PHASE")


def _heartbeat(sources: Sources, _device: Device) -> int:
    return sources.snapshot.step_id % 65536


def _inverter_kv(sources: Sources, device: Device) -> float:
    assets = sources.config.bess if device.kind is DeviceKind.BESS else sources.config.pv
    return next(asset.inverter.v_lv_kv for asset in assets if asset.id == device.asset_id)


def _v_nom(sources: Sources, device: Device) -> float:
    return _inverter_kv(sources, device) * KILO


def _a_max(sources: Sources, device: Device) -> float:
    return _current_a(_setpoint(sources, device, "s_rated_kva"), _inverter_kv(sources, device))


def _totals(attribute: str) -> Resolver:
    """A counter of the device's own powerflow asset (see counters.Totals)."""

    def resolve(sources: Sources, device: Device) -> float:
        return float(getattr(sources.counters.totals(powerflow_prefix(device)), attribute))

    return resolve


def _grid_hz(sources: Sources, _device: Device) -> float:
    return GRID_HZ.value_at(sources.snapshot.sim_time, sources.config.simulation.seed)


COMMON: dict[str, Resolver] = {"Hb": _heartbeat, "ACType": _ac_type}
DER_COMMON: dict[str, Resolver] = {**COMMON, "VNomRtg": _v_nom, "AMaxRtg": _a_max}


# -- BESS --------------------------------------------------------------------------------------


def _bess_sv(sources: Sources, device: Device) -> tuple[float, float]:
    bess = _bess(sources, device)
    return bess.s_kva, bess.v_lv_kv


def _bess_inv_state(sources: Sources, device: Device) -> int:
    bess = _bess(sources, device)
    if bess.status == BessStatus.OFFLINE:
        symbol = "OFF"
    elif bess.status == BessStatus.FAULT or bess.operating_state == BessOperatingState.FAULT:
        symbol = "FAULT"
    elif bess.operating_state in (BessOperatingState.CHARGING, BessOperatingState.DISCHARGING):
        symbol = "THROTTLED" if bess.limit_flags else "RUNNING"
    else:
        symbol = "STANDBY"
    return sources.enums.code("701.InvSt", symbol)


def _bess_cha_state(sources: Sources, device: Device) -> int:
    bess = _bess(sources, device)
    match BessOperatingState(bess.operating_state):
        case BessOperatingState.CHARGING:
            symbol = "CHARGING"
        case BessOperatingState.DISCHARGING:
            symbol = "DISCHARGING"
        case BessOperatingState.OFF | BessOperatingState.FAULT:
            symbol = "OFF"
        case BessOperatingState.STANDBY:
            soc_max = _setpoint(sources, device, "soc_max_pct")
            soc_min = _setpoint(sources, device, "soc_min_pct")
            if bess.soc_pct >= soc_max - STATE_MARGIN_PCT:
                symbol = "FULL"
            elif bess.soc_pct <= soc_min + STATE_MARGIN_PCT:
                symbol = "EMPTY"
            else:
                symbol = "HOLDING"
    return sources.enums.code("802.ChaSt", symbol)


def _bess_state(sources: Sources, device: Device) -> int:
    bess = _bess(sources, device)
    if bess.status == BessStatus.OFFLINE:
        symbol = "DISCONNECTED"
    elif bess.status == BessStatus.FAULT:
        symbol = "FAULT"
    else:
        symbol = "CONNECTED"
    return sources.enums.code("802.State", symbol)


def _bess_mode(sources: Sources, device: Device) -> int:
    return int(_setpoint(sources, device, "mode_cmd"))


BESS: dict[str, Resolver] = {
    **DER_COMMON,
    **_per_phase_ac(_bess_sv),
    "Hz": _grid_hz,
    "PF": lambda sources, device: power_factor(
        _bess(sources, device).p_kw, _bess(sources, device).q_kvar
    ),
    "TotWhInj": _totals("wh_positive"),
    "TotWhAbs": _totals("wh_negative"),
    "TotVarhInj": _totals("varh_positive"),
    "TotVarhAbs": _totals("varh_negative"),
    "St": lambda sources, device: sources.enums.code(
        "701.St", "OFF" if _bess(sources, device).status == BessStatus.OFFLINE else "ON"
    ),
    "InvSt": _bess_inv_state,
    "ConnSt": lambda sources, device: sources.enums.code(
        "701.ConnSt",
        "DISCONNECTED" if _bess(sources, device).status == BessStatus.OFFLINE else "CONNECTED",
    ),
    "DERMode": lambda sources, _device: sources.enums.bits("701.DERMode", "GRID_FOLLOWING"),
    "Alrm": lambda sources, device: _map_bits(
        sources,
        _bess(sources, device).alarm_flags,
        "701.Alrm",
        {
            BessAlarm.UNDERVOLTAGE: "AC_UNDER_VOLT",
            BessAlarm.OVERVOLTAGE: "AC_OVER_VOLT",
            BessAlarm.OVER_TEMPERATURE: "OVER_TEMP",
        },
    ),
    "ThrotSrc": lambda sources, device: _map_bits(
        sources,
        _bess(sources, device).limit_flags,
        "701.ThrotSrc",
        {
            BessFlag.P_LIMIT: "MAX_W",
            BessFlag.S_LIMIT: "MAX_W",
            BessFlag.SOC_LIMIT: "DERATED",
            BessFlag.RAMP_LIMIT: "DERATED",
        },
    ),
    "ChaSt": _bess_cha_state,
    "State": _bess_state,
    "LocRemCtl": lambda sources, _device: sources.enums.code("802.LocRemCtl", "REMOTE"),
    "Evt1": lambda sources, device: _map_bits(
        sources,
        _bess(sources, device).alarm_flags,
        "802.Evt1",
        {
            BessAlarm.SOC_LOW_WARNING: "UNDER_SOC_MIN_WARNING",
            BessAlarm.SOC_HIGH_WARNING: "OVER_SOC_MAX_WARNING",
            BessAlarm.OVER_TEMPERATURE: "OVER_TEMP_WARNING",
            BessAlarm.COMM_LOSS: "COMMUNICATION_ERROR",
        },
    ),
    "DoD": lambda sources, device: 100.0 - _bess(sources, device).soc_pct,
    "NCyc": lambda sources, device: math.floor(
        sources.counters.totals(powerflow_prefix(device)).wh_positive
        / (_setpoint(sources, device, "capacity_kwh") * KILO)
    ),
    "WSetEna": lambda sources, device: _ena(sources, _bess_mode(sources, device) == MODE_PQ),
    "WSetMod": lambda sources, _device: sources.enums.code("704.WSetMod", "WATTS"),
    "WSetPct": lambda sources, device: (
        _setpoint(sources, device, "p_setpoint_kw")
        / _setpoint(sources, device, "p_rated_discharge_kw")
        * 100.0
    ),
    "VarSetEna": lambda sources, device: _ena(sources, _bess_mode(sources, device) == MODE_PQ),
    "VarSetMod": lambda sources, _device: sources.enums.code("704.VarSetMod", "VARS"),
    "SetOp": lambda sources, device: sources.enums.code(
        "802.SetOp", "DISCONNECT" if _bess_mode(sources, device) == MODE_OFFLINE else "CONNECT"
    ),
    "SetInvState": lambda sources, device: sources.enums.code(
        "802.SetInvState",
        {MODE_PQ: "INVERTER_STARTED", MODE_OFFLINE: "INVERTER_STOPPED"}.get(
            _bess_mode(sources, device), "INVERTER_STANDBY"
        ),
    ),
}


# -- PV ----------------------------------------------------------------------------------------


def _pv_sv(sources: Sources, device: Device) -> tuple[float, float]:
    pv = _pv(sources, device)
    return pv.s_kva, pv.v_lv_kv


PV_INV_STATE: dict[PvInverterState, str] = {
    PvInverterState.OFF: "OFF",
    PvInverterState.SLEEPING: "SLEEPING",
    PvInverterState.MPPT: "RUNNING",
    PvInverterState.THROTTLED: "THROTTLED",
    PvInverterState.FAULT: "FAULT",
}


def _pv_q_mode(sources: Sources, device: Device) -> int:
    return int(_setpoint(sources, device, "q_mode"))


PV: dict[str, Resolver] = {
    **DER_COMMON,
    **_per_phase_ac(_pv_sv),
    "Hz": _grid_hz,
    "TotWhInj": _totals("wh_positive"),
    "TotWhAbs": _totals("wh_negative"),
    "WhInjDay": _totals("wh_positive_today"),
    "St": lambda sources, device: sources.enums.code(
        "701.St",
        "OFF" if _pv(sources, device).inverter_state == PvInverterState.OFF else "ON",
    ),
    "InvSt": lambda sources, device: sources.enums.code(
        "701.InvSt", PV_INV_STATE[PvInverterState(_pv(sources, device).inverter_state)]
    ),
    "ConnSt": lambda sources, device: sources.enums.code(
        "701.ConnSt",
        "DISCONNECTED" if _pv(sources, device).status == PvStatus.OFFLINE else "CONNECTED",
    ),
    "Alrm": lambda sources, device: _map_bits(
        sources,
        _pv(sources, device).alarm_flags,
        "701.Alrm",
        {
            PvAlarm.UNDERVOLTAGE: "AC_UNDER_VOLT",
            PvAlarm.OVERVOLTAGE: "AC_OVER_VOLT",
            PvAlarm.GROUND_FAULT: "GROUND_FAULT",
            PvAlarm.DC_OVERVOLTAGE: "DC_OVER_VOLT",
        },
    ),
    "DERMode": lambda sources, device: (
        sources.enums.bits("701.DERMode", "GRID_FOLLOWING")
        | _map_bits(
            sources, _pv(sources, device).limit_flags, "701.DERMode", {PvFlag.CLIPPED: "PV_CLIPPED"}
        )
    ),
    "ThrotPct": lambda sources, device: (
        _pv(sources, device).p_limit_active_kw / _setpoint(sources, device, "p_max_kw") * 100.0
    ),
    "ThrotSrc": lambda sources, device: _map_bits(
        sources,
        _pv(sources, device).limit_flags,
        "701.ThrotSrc",
        {PvFlag.CURTAILED: "FIXED_W", PvFlag.S_LIMIT: "MAX_W", PvFlag.CLIPPED: "MAX_W"},
    ),
    "WMaxLimPctEna": lambda sources, device: _ena(
        sources,
        _setpoint(sources, device, "p_limit_kw") < _setpoint(sources, device, "p_max_kw"),
    ),
    "VarSetEna": lambda sources, device: _ena(sources, _pv_q_mode(sources, device) == PvQMode.Q),
    "VarSetMod": lambda sources, _device: sources.enums.code("704.VarSetMod", "VARS"),
    "PFWInjEna": lambda sources, device: _ena(sources, _pv_q_mode(sources, device) == PvQMode.PF),
    "PFWInj": lambda sources, device: abs(_setpoint(sources, device, "pf_setpoint")),
    "PFWInjExt": lambda sources, device: sources.enums.code(
        "704.PFExt",
        "OVER_EXCITED" if _setpoint(sources, device, "pf_setpoint") >= 0 else "UNDER_EXCITED",
    ),
}


# -- loads -------------------------------------------------------------------------------------


def _load_v_kv(sources: Sources, device: Device) -> float:
    config = next(load for load in sources.config.loads if load.id == device.asset_id)
    nominal_kv = (
        config.transformer.vn_lv_kv if config.transformer is not None else sources.config.grid.vn_kv
    )
    return _load(sources, device).v_pu * nominal_kv


def _load_current(sources: Sources, device: Device) -> float:
    return _current_a(_load(sources, device).s_kva, _load_v_kv(sources, device))


LOAD: dict[str, Resolver] = {
    **COMMON,
    "PPV": lambda sources, device: _load_v_kv(sources, device) * KILO,
    "A": _load_current,
    "AphA": _load_current,
    "AphB": _load_current,
    "AphC": _load_current,
    "TotWhImp": _totals("wh_positive"),  # load convention: + consuming
}


# -- meters (POI and feeder) -------------------------------------------------------------------


def _meter_v_ll(sources: Sources, device: Device) -> float:
    return _meter(sources, device).v_kv * KILO


def _meter_v_ln(sources: Sources, device: Device) -> float:
    return _meter_v_ll(sources, device) / SQRT3


def _phase_share(attribute: str) -> Resolver:
    def resolve(sources: Sources, device: Device) -> float:
        return float(getattr(_meter(sources, device), attribute)) * KILO / 3.0

    return resolve


def _meter_current(sources: Sources, device: Device) -> float:
    return _meter(sources, device).i_a


def _meter_pf(sources: Sources, device: Device) -> float:
    return _meter(sources, device).pf


def _quadrant(index: int) -> Resolver:
    def resolve(sources: Sources, device: Device) -> float:
        return sources.counters.totals(powerflow_prefix(device)).varh_quadrant[index]

    return resolve


def _meter_events(sources: Sources, device: Device) -> int:
    meter = _meter(sources, device)
    alarms = status.meter_alarms(meter.p_kw, meter.v_pu, meter.pf, meter.s_kva)
    return _map_bits(
        sources,
        alarms,
        "203.Evt",
        {
            MeterAlarm.UNDERVOLTAGE: "M_EVENT_Under_Voltage",
            MeterAlarm.OVERVOLTAGE: "M_EVENT_Over_Voltage",
            MeterAlarm.LOW_POWER_FACTOR: "M_EVENT_Low_PF",
        },
    )


METER: dict[str, Resolver] = {
    **COMMON,
    "Hz": _grid_hz,
    "AphA": _meter_current,
    "AphB": _meter_current,
    "AphC": _meter_current,
    "AN": lambda _sources, _device: 0.0,
    "PhV": _meter_v_ln,
    "PhVphA": _meter_v_ln,
    "PhVphB": _meter_v_ln,
    "PhVphC": _meter_v_ln,
    "PhVphAB": _meter_v_ll,
    "PhVphBC": _meter_v_ll,
    "PhVphCA": _meter_v_ll,
    "WphA": _phase_share("p_kw"),
    "WphB": _phase_share("p_kw"),
    "WphC": _phase_share("p_kw"),
    "VARphA": _phase_share("q_kvar"),
    "VARphB": _phase_share("q_kvar"),
    "VARphC": _phase_share("q_kvar"),
    "VAphA": _phase_share("s_kva"),
    "VAphB": _phase_share("s_kva"),
    "VAphC": _phase_share("s_kva"),
    "PFphA": _meter_pf,
    "PFphB": _meter_pf,
    "PFphC": _meter_pf,
    "TotWhExp": _totals("wh_positive"),  # + = the meter's reference direction
    "TotWhImp": _totals("wh_negative"),
    "TotVAhExp": _totals("vah_positive"),
    "TotVAhImp": _totals("vah_negative"),
    "TotVArhImpQ1": _quadrant(0),
    "TotVArhImpQ2": _quadrant(1),
    "TotVArhExpQ3": _quadrant(2),
    "TotVArhExpQ4": _quadrant(3),
    "VUnb": lambda _sources, _device: 0.0,
    "AUnb": lambda _sources, _device: 0.0,
    "Evt": _meter_events,
}


# -- site (plant controller) and met station ---------------------------------------------------


def _pv_total(attribute: str) -> Resolver:
    return lambda sources, _device: (
        sum(float(getattr(pv, attribute)) for pv in sources.snapshot.pv) * KILO
    )


def _bess_total(attribute: str) -> Resolver:
    return lambda sources, _device: (
        sum(float(getattr(bess, attribute)) for bess in sources.snapshot.bess) * KILO
    )


def _pv_counter_total(attribute: str) -> Resolver:
    return lambda sources, _device: sum(
        float(getattr(sources.counters.totals(f"pv.{pv.id}"), attribute))
        for pv in sources.snapshot.pv
    )


def _fleet_soc(sources: Sources, _device: Device) -> float:
    capacity = {bess.id: bess.battery.capacity_kwh for bess in sources.config.bess}
    total = sum(capacity.values())
    if total <= 0:
        return 0.0
    return sum(bess.soc_pct * capacity[bess.id] for bess in sources.snapshot.bess) / total


def _count_inverters(*states: PvInverterState) -> Resolver:
    return lambda sources, _device: sum(
        1 for pv in sources.snapshot.pv if PvInverterState(pv.inverter_state) in states
    )


def _site_alarms(sources: Sources, _device: Device) -> int:
    stale = sources.snapshot.poi.meter_state == MeterState.STALE
    return sources.enums.bits("pae.PpcAlrm", "POI_METER_FAIL") if stale else 0


SITE: dict[str, Resolver] = {
    **COMMON,
    "SiteHz": _grid_hz,
    "PvW": _pv_total("p_kw"),
    "PvVar": _pv_total("q_kvar"),
    "PvWAvail": _pv_total("p_available_kw"),
    "PvWhDay": _pv_counter_total("wh_positive_today"),
    "PvTotWh": _pv_counter_total("wh_positive"),
    "BessW": _bess_total("p_kw"),
    "BessVar": _bess_total("q_kvar"),
    "BessSoC": _fleet_soc,
    "BessWAvailDisCha": _bess_total("p_available_discharge_kw"),
    "BessWAvailCha": _bess_total("p_available_charge_kw"),
    "BessWHAvailDisCha": _bess_total("energy_available_discharge_kwh"),
    "NInvAvail": _count_inverters(
        PvInverterState.OFF,
        PvInverterState.SLEEPING,
        PvInverterState.MPPT,
        PvInverterState.THROTTLED,
    ),
    "NInvRun": _count_inverters(PvInverterState.MPPT, PvInverterState.THROTTLED),
    "NInvStby": _count_inverters(PvInverterState.OFF, PvInverterState.SLEEPING),
    "NInvFlt": _count_inverters(PvInverterState.FAULT),
    "NInvDrt": _count_inverters(PvInverterState.THROTTLED),
    "GridMode": lambda sources, _device: sources.enums.code("pae.GridMode", "GRID_TIED"),
    "Alrm": _site_alarms,
}


def _ghi(sources: Sources, _device: Device) -> float | None:
    irradiance_ids = [
        pv.id
        for pv in sources.config.pv
        if pv.availability.source is PvAvailabilitySource.IRRADIANCE
    ]
    readings = [pv.irradiance_wm2 for pv in sources.snapshot.pv if pv.id in irradiance_ids]
    return readings[0] if readings else None


MET_STATION: dict[str, Resolver] = {**COMMON, "GHI": _ghi}


CALC_RESOLVERS: dict[DeviceKind, dict[str, Resolver]] = {
    DeviceKind.SITE: SITE,
    DeviceKind.MET_STATION: MET_STATION,
    DeviceKind.BESS: BESS,
    DeviceKind.PV: PV,
    DeviceKind.LOAD: LOAD,
    DeviceKind.POI_METER: METER,
    DeviceKind.FEEDER_METER: METER,
}
