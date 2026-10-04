"""`powerflow_server = calc` points: values derived from the simulation results.

- **Balanced network:** the solver is positive-sequence, so every phase carries the same
  current and a third of the power, L-L voltages are equal, L-N = L-L/√3, and unbalance is 0.
- **Currents:** I = S/(√3·V_LL) (kVA/kV = A).
- **States and alarms:** powerflow's own status/flag codes, translated to the SunSpec/PAE codes
  in enums.csv by symbol name, so the numbers come from the standard.
- **Energy:** the counters the simulation keeps on each snapshot measurement (`energy`).
- **Site:** fleet sums over the BESS and PV assets.
- **Frequency:** the snapshot's grid frequency (`poi.hz`: nominal or an injected excursion,
  plus a small wander), the same for every device; 0 on a de-energised device.
- **Injected conditions:** a comm-lost device publishes frozen values (the snapshot already holds
  them) and a frozen heartbeat; `BrkPos` is the device's breaker (the site and POI meter: the
  POI breaker; a feeder meter: its asset's).
"""

import math
from collections.abc import Callable, Sequence
from typing import Protocol, TypeVar

from powerflow.conditions import CommTarget
from powerflow.core.snapshot import (
    BessMeasurement,
    EnergyTotals,
    LoadMeasurement,
    MeterMeasurement,
    PoiMeasurement,
    PvMeasurement,
)
from powerflow.models import status
from powerflow.models.bess import BESS_MODE_CODES, BessFlag, BessMode, BessStatus
from powerflow.models.common import power_factor
from powerflow.models.pv import PvFlag, PvQMode, PvStatus
from powerflow.models.status import (
    BessAlarm,
    BessOperatingState,
    BreakerState,
    MeterAlarm,
    MeterState,
    PvAlarm,
    PvInverterState,
)
from powerflow.point_standard.layout import Device, DeviceKind
from powerflow.point_standard.sources import Resolver, Sources, powerflow_prefix
from powerflow.site_config import PvAvailabilitySource

SQRT3 = math.sqrt(3.0)
KILO = 1000.0
MODE_PQ = BESS_MODE_CODES[BessMode.PQ]  # the mode_cmd point's codes
MODE_OFFLINE = BESS_MODE_CODES[BessMode.OFFLINE]
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


def _comm_key(device: Device) -> tuple[CommTarget, str | None] | None:
    """The comm-loss target a device answers for (the site and met station: none)."""
    match device.kind:
        case DeviceKind.BESS | DeviceKind.PV | DeviceKind.LOAD:
            return CommTarget.ASSET, device.asset_id
        case DeviceKind.FEEDER_METER:
            return CommTarget.METER, device.asset_id
        case DeviceKind.POI_METER:
            return CommTarget.POI_METER, None
        case DeviceKind.SITE | DeviceKind.MET_STATION:
            return None


def _heartbeat(sources: Sources, device: Device) -> int:
    """The step counter; frozen at the step comm was lost, like a hung device."""
    conditions = sources.snapshot.conditions
    key = _comm_key(device)
    if conditions is not None and key is not None:
        for lost in conditions.comm_loss:
            if (lost.target, lost.id) == key:
                return lost.since_step % 65536
    return sources.snapshot.step_id % 65536


def _breaker_pos(sources: Sources, device: Device) -> int | None:
    snapshot = sources.snapshot
    match device.kind:
        case DeviceKind.BESS:
            state = _bess(sources, device).breaker_state
        case DeviceKind.PV:
            state = _pv(sources, device).breaker_state
        case DeviceKind.LOAD:
            state = _load(sources, device).breaker_state
        case DeviceKind.FEEDER_METER:
            asset_id = next(
                meter.transformer for meter in sources.config.meters if meter.id == device.asset_id
            )
            assets = [*snapshot.bess, *snapshot.pv, *snapshot.loads]
            state = next(asset.breaker_state for asset in assets if asset.id == asset_id)
        case DeviceKind.POI_METER | DeviceKind.SITE:
            state = snapshot.poi.breaker_state
        case DeviceKind.MET_STATION:
            return None
    symbol = "CLOSED" if state == BreakerState.CLOSED else "OPEN"
    return sources.enums.code("pae.Dbpos", symbol)


def _inverter_kv(sources: Sources, device: Device) -> float:
    assets = sources.config.bess if device.kind is DeviceKind.BESS else sources.config.pv
    return next(asset.inverter.v_lv_kv for asset in assets if asset.id == device.asset_id)


def _v_nom(sources: Sources, device: Device) -> float:
    return _inverter_kv(sources, device) * KILO


def _a_max(sources: Sources, device: Device) -> float:
    return _current_a(_setpoint(sources, device, "s_rated_kva"), _inverter_kv(sources, device))


def _energy(sources: Sources, device: Device) -> EnergyTotals:
    """The device's energy counters, from its snapshot measurement."""
    snapshot = sources.snapshot
    match device.kind:
        case DeviceKind.BESS:
            return _find(snapshot.bess, device).energy
        case DeviceKind.PV:
            return _find(snapshot.pv, device).energy
        case DeviceKind.LOAD:
            return _find(snapshot.loads, device).energy
        case DeviceKind.FEEDER_METER:
            return _find(snapshot.meters, device).energy
        case DeviceKind.POI_METER | DeviceKind.SITE | DeviceKind.MET_STATION:
            return snapshot.poi.energy


def _totals(attribute: str) -> Resolver:
    """One of the device's energy counters (see core/snapshot.EnergyTotals)."""

    def resolve(sources: Sources, device: Device) -> float:
        return float(getattr(_energy(sources, device), attribute))

    return resolve


def _device_v_pu(sources: Sources, device: Device) -> float:
    match device.kind:
        case DeviceKind.BESS:
            return _bess(sources, device).v_lv_pu
        case DeviceKind.PV:
            return _pv(sources, device).v_lv_pu
        case DeviceKind.LOAD:
            return _load(sources, device).v_pu
        case DeviceKind.POI_METER | DeviceKind.FEEDER_METER:
            return _meter(sources, device).v_pu
        case DeviceKind.SITE | DeviceKind.MET_STATION:
            return sources.snapshot.poi.v_pu


def _grid_hz(sources: Sources, device: Device) -> float:
    return sources.snapshot.poi.hz if _device_v_pu(sources, device) > 0 else 0.0


COMMON: dict[str, Resolver] = {"Hb": _heartbeat, "ACType": _ac_type, "BrkPos": _breaker_pos}
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
        "DISCONNECTED"
        if _bess(sources, device).status in (BessStatus.OFFLINE, BessStatus.FAULT)
        else "CONNECTED",
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
        _energy(sources, device).wh_positive / (_setpoint(sources, device, "capacity_kwh") * KILO)
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
        "DISCONNECTED"
        if _pv(sources, device).status in (PvStatus.OFFLINE, PvStatus.FAULT)
        else "CONNECTED",
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
            PvAlarm.COMM_LOSS: None,  # a comm-lost device can't report it; the site does
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
    "TotVArhImpQ1": _totals("varh_q1"),
    "TotVArhImpQ2": _totals("varh_q2"),
    "TotVArhExpQ3": _totals("varh_q3"),
    "TotVArhExpQ4": _totals("varh_q4"),
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
        float(getattr(pv.energy, attribute)) for pv in sources.snapshot.pv
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
    """POI meter STALE → POI_METER_FAIL; any comm-lost asset or feeder meter →
    DEVICE_COMM_LOSS (the plant controller notices a device stopped answering)."""
    snapshot = sources.snapshot
    value = 0
    if snapshot.poi.meter_state == MeterState.STALE:
        value |= sources.enums.bits("pae.PpcAlrm", "POI_METER_FAIL")
    conditions = snapshot.conditions
    if conditions is not None and any(
        lost.target is not CommTarget.POI_METER for lost in conditions.comm_loss
    ):
        value |= sources.enums.bits("pae.PpcAlrm", "DEVICE_COMM_LOSS")
    return value


def _grid_mode(sources: Sources, _device: Device) -> int:
    dead = sources.snapshot.poi.breaker_state == BreakerState.OPEN
    return sources.enums.code("pae.GridMode", "BLACKOUT" if dead else "GRID_TIED")


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
    "GridMode": _grid_mode,
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
