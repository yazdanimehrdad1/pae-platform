"""Protocol-neutral point lists, one per asset type.

A point's full name is `<asset_type>.<asset_id>.<point>`, e.g. `bess.bess1.soc_pct`,
`poi.meter.p_kw`, `meter.m_bess1.p_kw` (a feeder meter), `site.sim.step_id`. HTTP field names,
history `fields=` and PointRegistry use these names (the Modbus server's own names come from the
PAE point standard, which maps onto these).

`scale_hint` is the suggested resolution when a point is packed into an integer register
(engineering value = raw × scale).
"""

from enum import IntEnum, IntFlag, StrEnum

from pydantic import BaseModel, ConfigDict

from powerflow.models.bess import BESS_MODE_CODES, BessFlag, BessStatus
from powerflow.models.pv import PvFlag, PvQMode, PvStatus
from powerflow.models.status import (
    BessAlarm,
    BessOperatingState,
    LoadAlarm,
    LoadSupplyState,
    MeterAlarm,
    MeterState,
    PvAlarm,
    PvInverterState,
    SiteAlarm,
)

POI_ASSET_ID = "meter"
SITE_ASSET_ID = "sim"
# The engine state as the `site.sim.state` point encodes it (RunState values).
RUN_STATE_CODES: dict[str, int] = {"stopped": 0, "running": 1, "paused": 2}


class AssetType(StrEnum):
    BESS = "bess"
    PV = "pv"
    LOAD = "load"
    POI = "poi"
    SITE = "site"
    METER = "meter"  # feeder meters (`SiteConfig.meters`), named by meter id


class Access(StrEnum):
    READ = "R"
    READ_WRITE = "RW"


class DataType(StrEnum):
    FLOAT32 = "float32"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    ENUM16 = "enum16"
    BITFIELD16 = "bitfield16"


class PointSource(StrEnum):
    """Where a point's value comes from."""

    MEASUREMENT = "measurement"  # the latest snapshot (also available in history)
    SETPOINT = "setpoint"  # the setpoint store (what the asset applies next step)
    NAMEPLATE = "nameplate"  # the site config
    SIMULATION = "simulation"  # the engine's live status


class PointDef(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    unit: str
    data_type: DataType
    access: Access
    source: PointSource
    scale_hint: float | None = None
    enum_values: dict[int, str] | None = None
    bit_flags: dict[int, str] | None = None


def _measurement(name: str, description: str, unit: str, scale: float | None = 1.0) -> PointDef:
    return PointDef(
        name=name,
        description=description,
        unit=unit,
        data_type=DataType.FLOAT32,
        access=Access.READ,
        source=PointSource.MEASUREMENT,
        scale_hint=scale,
    )


def _nameplate(name: str, description: str, unit: str) -> PointDef:
    return PointDef(
        name=name,
        description=description,
        unit=unit,
        data_type=DataType.FLOAT32,
        access=Access.READ,
        source=PointSource.NAMEPLATE,
        scale_hint=1.0,
    )


def _flags(flag_type: type[IntFlag]) -> dict[int, str]:
    return {
        member.value.bit_length() - 1: member.name
        for member in flag_type
        if member.value and member.name
    }


def _state(name: str, description: str, states: type[IntEnum]) -> PointDef:
    return PointDef(
        name=name,
        description=description,
        unit="",
        data_type=DataType.ENUM16,
        access=Access.READ,
        source=PointSource.MEASUREMENT,
        enum_values={member.value: member.name for member in states},
    )


def _alarms(description: str, flags: type[IntFlag], source: PointSource) -> PointDef:
    return PointDef(
        name="alarm_flags",
        description=description,
        unit="",
        data_type=DataType.BITFIELD16,
        access=Access.READ,
        source=source,
        bit_flags=_flags(flags),
    )


VOLTAGE_ALARM_NOTE = "voltage outside 0.95-1.05 pu"
RESERVED_NOTE = "Bits marked reserved in the model aren't set by the simulator yet."
ENERGY_NOTE = "Integrated every converged step since the simulation started (reset/activate)."


BESS_POINTS: tuple[PointDef, ...] = (
    PointDef(
        name="p_setpoint_kw",
        description="Active power setpoint. + discharge, − charge. Clamped to the P ratings "
        "and the S circle on write.",
        unit="kW",
        data_type=DataType.FLOAT32,
        access=Access.READ_WRITE,
        source=PointSource.SETPOINT,
        scale_hint=1.0,
    ),
    PointDef(
        name="q_setpoint_kvar",
        description="Reactive power setpoint. + injecting vars.",
        unit="kvar",
        data_type=DataType.FLOAT32,
        access=Access.READ_WRITE,
        source=PointSource.SETPOINT,
        scale_hint=1.0,
    ),
    PointDef(
        name="mode_cmd",
        description="Operating mode command.",
        unit="",
        data_type=DataType.ENUM16,
        access=Access.READ_WRITE,
        source=PointSource.SETPOINT,
        enum_values={code: mode.value for mode, code in BESS_MODE_CODES.items()},
    ),
    _measurement("p_cmd_kw", "P the inverter is commanded (after mode and static limits).", "kW"),
    _measurement("q_cmd_kvar", "Q the inverter is commanded.", "kvar"),
    _measurement("p_kw", "Actual active power. + discharge, − charge.", "kW"),
    _measurement("q_kvar", "Actual reactive power. + injecting vars.", "kvar"),
    _measurement("s_kva", "Actual apparent power.", "kVA"),
    _measurement("soc_pct", "State of charge.", "%", 0.1),
    _measurement("energy_available_discharge_kwh", "AC energy until SOC min.", "kWh"),
    _measurement("energy_available_charge_kwh", "AC energy until SOC max.", "kWh"),
    _measurement("p_available_discharge_kw", "Max discharge P now (ratings and SOC).", "kW"),
    _measurement("p_available_charge_kw", "Max charge P now (ratings and SOC), ≥ 0.", "kW"),
    PointDef(
        name="status",
        description="Operating status.",
        unit="",
        data_type=DataType.ENUM16,
        access=Access.READ,
        source=PointSource.MEASUREMENT,
        enum_values={member.value: member.name for member in BessStatus},
    ),
    PointDef(
        name="limit_flags",
        description="Limits active this step.",
        unit="",
        data_type=DataType.BITFIELD16,
        access=Access.READ,
        source=PointSource.MEASUREMENT,
        bit_flags=_flags(BessFlag),
    ),
    _measurement("aux_p_kw", "Auxiliary load, drawn from the LV bus.", "kW"),
    _measurement("v_lv_pu", "Inverter terminal (LV bus) voltage.", "pu", 0.001),
    _measurement("v_lv_kv", "Inverter terminal voltage, line-to-line.", "kV", 0.001),
    _state("operating_state", "Operating state (derived from mode and P).", BessOperatingState),
    _alarms(
        f"Alarms: SOC within 5 % of a limit, {VOLTAGE_ALARM_NOTE}, transformer > 100 %. "
        + RESERVED_NOTE,
        BessAlarm,
        PointSource.MEASUREMENT,
    ),
    _measurement("energy_discharged_kwh", f"AC energy discharged. {ENERGY_NOTE}", "kWh"),
    _measurement("energy_charged_kwh", f"AC energy charged. {ENERGY_NOTE}", "kWh"),
    _nameplate("p_rated_discharge_kw", "Max discharge P.", "kW"),
    _nameplate("p_rated_charge_kw", "Max charge P (magnitude).", "kW"),
    _nameplate("s_rated_kva", "Inverter apparent power rating.", "kVA"),
    _nameplate("capacity_kwh", "Energy capacity.", "kWh"),
    _nameplate("soc_min_pct", "SOC lower limit.", "%"),
    _nameplate("soc_max_pct", "SOC upper limit.", "%"),
)

PV_POINTS: tuple[PointDef, ...] = (
    PointDef(
        name="p_limit_kw",
        description="Curtailment: max active power. Writing it replaces p_limit_pct.",
        unit="kW",
        data_type=DataType.FLOAT32,
        access=Access.READ_WRITE,
        source=PointSource.SETPOINT,
        scale_hint=1.0,
    ),
    PointDef(
        name="p_limit_pct",
        description="Curtailment as % of p_max_kw. Writing it replaces p_limit_kw.",
        unit="%",
        data_type=DataType.FLOAT32,
        access=Access.READ_WRITE,
        source=PointSource.SETPOINT,
        scale_hint=0.1,
    ),
    PointDef(
        name="q_setpoint_kvar",
        description="Reactive power setpoint (+ injecting). Writing it selects Q mode.",
        unit="kvar",
        data_type=DataType.FLOAT32,
        access=Access.READ_WRITE,
        source=PointSource.SETPOINT,
        scale_hint=1.0,
    ),
    PointDef(
        name="pf_setpoint",
        description="Power factor setpoint: + injecting vars, − absorbing; |pf| in [0.8, 1]. "
        "Writing it selects PF mode.",
        unit="",
        data_type=DataType.FLOAT32,
        access=Access.READ_WRITE,
        source=PointSource.SETPOINT,
        scale_hint=0.001,
    ),
    PointDef(
        name="q_mode",
        description="Active reactive power control mode.",
        unit="",
        data_type=DataType.ENUM16,
        access=Access.READ,
        source=PointSource.SETPOINT,
        enum_values={member.value: member.name for member in PvQMode},
    ),
    _measurement("p_available_kw", "Available AC power (after losses and clipping).", "kW"),
    _measurement("p_limit_active_kw", "Curtailment limit applied this step.", "kW"),
    _measurement("p_kw", "Actual active power.", "kW"),
    _measurement("q_kvar", "Actual reactive power. + injecting vars.", "kvar"),
    _measurement("s_kva", "Actual apparent power.", "kVA"),
    _measurement("pf", "Power factor, signed with Q.", "", 0.001),
    _measurement("curtailment_kw", "Available minus actual P.", "kW"),
    _measurement("irradiance_wm2", "Irradiance (irradiance source; else 0).", "W/m2"),
    PointDef(
        name="status",
        description="Operating status.",
        unit="",
        data_type=DataType.ENUM16,
        access=Access.READ,
        source=PointSource.MEASUREMENT,
        enum_values={member.value: member.name for member in PvStatus},
    ),
    PointDef(
        name="limit_flags",
        description="Limits active this step.",
        unit="",
        data_type=DataType.BITFIELD16,
        access=Access.READ,
        source=PointSource.MEASUREMENT,
        bit_flags=_flags(PvFlag),
    ),
    _measurement("v_lv_pu", "Inverter terminal (LV bus) voltage.", "pu", 0.001),
    _measurement("v_lv_kv", "Inverter terminal voltage, line-to-line.", "kV", 0.001),
    _state(
        "inverter_state",
        "Inverter state (derived from availability and curtailment).",
        PvInverterState,
    ),
    _alarms(
        f"Alarms: {VOLTAGE_ALARM_NOTE}, transformer > 100 %. " + RESERVED_NOTE,
        PvAlarm,
        PointSource.MEASUREMENT,
    ),
    _measurement("energy_produced_kwh", f"AC energy produced. {ENERGY_NOTE}", "kWh"),
    _measurement(
        "energy_produced_today_kwh", "AC energy produced since the sim day began (UTC).", "kWh"
    ),
    _nameplate("dc_kwp", "DC capacity.", "kWp"),
    _nameplate("p_max_kw", "Inverter max AC active power.", "kW"),
    _nameplate("s_rated_kva", "Inverter apparent power rating.", "kVA"),
)

LOAD_POINTS: tuple[PointDef, ...] = (
    _measurement("p_kw", "Active power. + consuming.", "kW"),
    _measurement("q_kvar", "Reactive power. + consuming vars (lagging).", "kvar"),
    _measurement("s_kva", "Apparent power.", "kVA"),
    _measurement("pf", "Power factor, signed with Q (+ lagging).", "", 0.001),
    _measurement("v_pu", "Voltage at the load's bus.", "pu", 0.001),
    _state("supply_state", "Whether the load's bus is energized.", LoadSupplyState),
    _alarms(f"Alarms: {VOLTAGE_ALARM_NOTE}.", LoadAlarm, PointSource.MEASUREMENT),
    _measurement("energy_consumed_kwh", f"Energy consumed. {ENERGY_NOTE}", "kWh"),
)

POI_POINTS: tuple[PointDef, ...] = (
    _measurement("p_kw", "Active power. + export to the utility, − import.", "kW"),
    _measurement("q_kvar", "Reactive power. + export.", "kvar"),
    _measurement("s_kva", "Apparent power.", "kVA"),
    _measurement("pf", "Power factor, signed with Q (+ exporting vars).", "", 0.001),
    _measurement("v_kv", "POI voltage, line-to-line.", "kV", 0.001),
    _measurement("v_pu", "POI voltage.", "pu", 0.001),
    _measurement("angle_deg", "POI voltage angle (source = 0).", "deg", 0.01),
    _measurement("i_a", "POI current.", "A", 0.1),
    _measurement("p_loss_total_kw", "Site losses: transformers + collector feeders.", "kW"),
    _measurement("q_loss_total_kvar", "Site reactive losses.", "kvar"),
    _state(
        "meter_state", "STALE when the power flow didn't converge (last good values).", MeterState
    ),
    _alarms(
        f"Alarms: {VOLTAGE_ALARM_NOTE}, exporting / importing (|P| > 1 kW), |pf| < 0.9.",
        MeterAlarm,
        PointSource.MEASUREMENT,
    ),
    _measurement("energy_export_kwh", f"Energy exported to the utility. {ENERGY_NOTE}", "kWh"),
    _measurement("energy_import_kwh", f"Energy imported from the utility. {ENERGY_NOTE}", "kWh"),
)

METER_POINTS: tuple[PointDef, ...] = (
    _measurement("p_kw", "Active power on the transformer's HV side. + toward the MV bus.", "kW"),
    _measurement("q_kvar", "Reactive power. + toward the MV bus.", "kvar"),
    _measurement("s_kva", "Apparent power.", "kVA"),
    _measurement("pf", "Power factor, signed with Q.", "", 0.001),
    _measurement("v_kv", "MV bus voltage, line-to-line.", "kV", 0.001),
    _measurement("v_pu", "MV bus voltage.", "pu", 0.001),
    _measurement("i_a", "Current on the transformer's HV side.", "A", 0.1),
    _state(
        "meter_state", "STALE when the power flow didn't converge (last good values).", MeterState
    ),
    _measurement("energy_export_kwh", f"Energy toward the MV bus. {ENERGY_NOTE}", "kWh"),
    _measurement("energy_import_kwh", f"Energy from the MV bus. {ENERGY_NOTE}", "kWh"),
)

SITE_POINTS: tuple[PointDef, ...] = (
    PointDef(
        name="step_id",
        description="Sim tick of the latest snapshot (gaps = skipped ticks).",
        unit="",
        data_type=DataType.UINT64,
        access=Access.READ,
        source=PointSource.MEASUREMENT,
    ),
    PointDef(
        name="sim_time_epoch_s",
        description="Sim time of the latest snapshot (Unix s).",
        unit="s",
        data_type=DataType.UINT64,
        access=Access.READ,
        source=PointSource.MEASUREMENT,
    ),
    PointDef(
        name="converged",
        description="1 if the latest power flow converged.",
        unit="",
        data_type=DataType.UINT16,
        access=Access.READ,
        source=PointSource.MEASUREMENT,
    ),
    PointDef(
        name="state",
        description="Engine state.",
        unit="",
        data_type=DataType.ENUM16,
        access=Access.READ,
        source=PointSource.SIMULATION,
        enum_values={code: name for name, code in RUN_STATE_CODES.items()},
    ),
    PointDef(
        name="overrun_count",
        description="Real-time ticks skipped because a step overran.",
        unit="",
        data_type=DataType.UINT32,
        access=Access.READ,
        source=PointSource.SIMULATION,
    ),
    _alarms(
        "Alarms: latest power flow not converged, a real-time overrun since reset, test mode.",
        SiteAlarm,
        PointSource.SIMULATION,
    ),
)

POINT_LISTS: dict[AssetType, tuple[PointDef, ...]] = {
    AssetType.BESS: BESS_POINTS,
    AssetType.PV: PV_POINTS,
    AssetType.LOAD: LOAD_POINTS,
    AssetType.POI: POI_POINTS,
    AssetType.SITE: SITE_POINTS,
    AssetType.METER: METER_POINTS,
}


def point_def(asset_type: AssetType, point: str) -> PointDef | None:
    return next((item for item in POINT_LISTS[asset_type] if item.name == point), None)
