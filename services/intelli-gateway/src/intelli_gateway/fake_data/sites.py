"""Two fictional sites for development and tests: devices, topology, points, alarm rules,
knowledge documents and engineer point guides.

Everything here is invented. Values are deterministic functions of time computed by the plant
model in fake_data/site_data.py, so they hang together: INV2's status, output, alarm word and
fault code all follow its cabinet temperature.
"""

from datetime import UTC, datetime

from intelli_gateway.fake_data.models import (
    AlarmRule,
    BitRule,
    FakePoint,
    FakeSite,
    Signal,
    SignalShape,
    StaticAlarmEvent,
)
from intelli_gateway.schemas.knowledge import (
    GuideSeverity,
    KnowledgeDocument,
    KnowledgeKind,
    LimitCondition,
    LimitGuide,
    NormalRange,
    PointGuide,
    StateGuide,
    StateKind,
)
from intelli_gateway.schemas.site_data import (
    AlarmSeverity,
    Device,
    PointClass,
    PointInfo,
    Site,
    Topology,
    TopologyConnection,
    TopologyNode,
)

_UPDATED = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
_SOLAR_PHASE = 1.0  # roughly CET

INVERTER_STATES = {0: "OFF", 1: "SLEEPING", 3: "RUNNING", 4: "DERATED", 6: "FAULT"}
INVERTER_ALARM_BITS = {
    0: "GROUND_FAULT",
    1: "DC_OVER_VOLT",
    2: "GRID_DISCONNECT",
    3: "CABINET_OPEN",
    4: "OVER_TEMP",
    5: "FAN_FAULT",
}
BESS_STATES = {1: "STANDBY", 2: "CHARGING", 3: "DISCHARGING", 99: "FAULT"}
TURBINE_STATES = {0: "STOPPED", 1: "RUNNING", 2: "CURTAILED", 3: "FAULT"}
DERATE_AT_C = 60.0
TRIP_AT_C = 75.0


def _point(
    name: str,
    description: str,
    unit: str | None,
    device: Device,
    equipment: str,
    signal: Signal,
    point_class: PointClass = PointClass.ANALOG,
    data_type: str = "float32",
    severity: str | None = None,
    enum_labels: dict[int, str] | None = None,
    bit_labels: dict[int, str] | None = None,
) -> FakePoint:
    return FakePoint(
        info=PointInfo(
            name=name,
            description=description,
            unit=unit,
            device_id=device.device_id,
            device_name=device.name,
            equipment=equipment,
            data_type=data_type,
            point_class=point_class,
            severity=severity,
            enum_labels=enum_labels or {},
            bit_labels=bit_labels or {},
        ),
        signal=signal,
    )


def _inverter_points(device: Device, temp_base: float) -> tuple[FakePoint, ...]:
    prefix = device.name
    return (
        _point(
            f"{prefix}.ActivePower",
            f"{prefix} AC active power",
            "kW",
            device,
            "inverter",
            Signal(
                shape=SignalShape.INVERTER_POWER,
                amplitude=2400,
                phase_hours=_SOLAR_PHASE,
                source=f"{prefix}.Status",
                limit=1500,
            ),
        ),
        _point(
            f"{prefix}.CabinetTemp",
            f"{prefix} cabinet temperature",
            "degC",
            device,
            "inverter",
            Signal(
                shape=SignalShape.DAILY_SINE, base=temp_base, amplitude=9, phase_hours=_SOLAR_PHASE
            ),
        ),
        _point(
            f"{prefix}.Status",
            f"{prefix} operating state",
            None,
            device,
            "inverter",
            Signal(
                shape=SignalShape.INVERTER_STATUS,
                phase_hours=_SOLAR_PHASE,
                source=f"{prefix}.CabinetTemp",
                threshold=DERATE_AT_C,
                trip=TRIP_AT_C,
            ),
            point_class=PointClass.BINARY,
            data_type="enum16",
            enum_labels=INVERTER_STATES,
        ),
        _point(
            f"{prefix}.AlarmWord",
            f"{prefix} alarm word",
            None,
            device,
            "inverter",
            Signal(
                shape=SignalShape.ALARM_WORD,
                bit_rules=(BitRule(bit=4, point=f"{prefix}.CabinetTemp", at_or_above=DERATE_AT_C),),
            ),
            point_class=PointClass.ALARM,
            data_type="bitfield16",
            severity="HIGH",
            bit_labels=INVERTER_ALARM_BITS,
        ),
        _point(
            f"{prefix}.FaultCode",
            f"{prefix} vendor fault code (0 = no fault)",
            None,
            device,
            "inverter",
            Signal(shape=SignalShape.FAULT_CODE, source=f"{prefix}.Status", threshold=6, code=101),
            point_class=PointClass.ALARM,
            data_type="uint16",
            severity="HIGH",
        ),
    )


def _inverter_guides(site_id: int, device: Device) -> tuple[PointGuide, ...]:
    """Fictional guides for one inverter. Per site device: each inverter has its own copy."""
    prefix = device.name
    temp, status, alarms, fault = (
        f"{prefix}.CabinetTemp",
        f"{prefix}.Status",
        f"{prefix}.AlarmWord",
        f"{prefix}.FaultCode",
    )
    power = f"{prefix}.ActivePower"
    cooling_causes = (
        "Clogged cabinet air intake filter",
        "Cabinet fan failed or running slow",
        "High ambient temperature with direct sun on the cabinet",
    )
    cooling_checks = (
        f"Compare {temp} with the other inverter's cabinet temperature",
        "Inspect and clean the intake filter",
        "Check the cabinet fan runs and its current draw is normal",
        "Check WS1.AmbientTemp for an unusually hot day",
    )
    lockout = "Isolate and lock out the inverter (AC and DC) before opening the cabinet."
    return (
        PointGuide(
            site_id=site_id,
            device_id=device.device_id,
            point_name=status,
            meaning=f"Operating state reported by {prefix}'s controller.",
            related_points=(power, temp, alarms, fault),
            updated_at=_UPDATED,
            author="field engineer (fictional)",
            states=(
                StateGuide(
                    kind=StateKind.ENUM_VALUE,
                    code=0,
                    label="OFF",
                    severity=GuideSeverity.WARNING,
                    message=f"{prefix} is switched off",
                    probable_causes=("Manual stop", "AC breaker open"),
                    checks=("Check the local HMI and the AC breaker position",),
                ),
                StateGuide(
                    kind=StateKind.ENUM_VALUE,
                    code=1,
                    label="SLEEPING",
                    severity=GuideSeverity.INFO,
                    message="No PV power available (night or very low irradiance)",
                    meaning="Normal at night.",
                    related_points=("WS1.Irradiance",),
                ),
                StateGuide(
                    kind=StateKind.ENUM_VALUE,
                    code=3,
                    label="RUNNING",
                    severity=GuideSeverity.INFO,
                    message="Producing normally",
                ),
                StateGuide(
                    kind=StateKind.ENUM_VALUE,
                    code=4,
                    label="DERATED",
                    severity=GuideSeverity.WARNING,
                    message=f"{prefix} limits its output to about 1500 kW",
                    meaning=(
                        f"The controller caps output while {temp} is at or above "
                        f"{DERATE_AT_C:g} degC to protect the power stage."
                    ),
                    probable_causes=cooling_causes,
                    checks=cooling_checks,
                    related_points=(temp, power, alarms),
                ),
                StateGuide(
                    kind=StateKind.ENUM_VALUE,
                    code=6,
                    label="FAULT",
                    severity=GuideSeverity.FAULT,
                    message=f"{prefix} tripped",
                    meaning=f"Stopped by a protection; {fault} says which one.",
                    checks=(f"Read {fault} and look it up", "Check the local event log"),
                    related_points=(fault, alarms, temp),
                    safety_note=lockout,
                ),
            ),
        ),
        PointGuide(
            site_id=site_id,
            device_id=device.device_id,
            point_name=temp,
            meaning=f"Air temperature inside {prefix}'s power cabinet.",
            normal_range=NormalRange(
                min=25, max=55, note="Follows ambient plus load; lower at night"
            ),
            related_points=(status, power, "WS1.AmbientTemp"),
            updated_at=_UPDATED,
            author="field engineer (fictional)",
            limits=(
                LimitGuide(
                    condition=LimitCondition.ABOVE,
                    value=DERATE_AT_C,
                    severity=GuideSeverity.WARNING,
                    message=f"Derating: {prefix} limits output to about 1500 kW",
                    probable_causes=cooling_causes,
                    checks=cooling_checks,
                ),
                LimitGuide(
                    condition=LimitCondition.ABOVE,
                    value=TRIP_AT_C,
                    severity=GuideSeverity.FAULT,
                    message=f"Over-temperature trip: {prefix} stops (fault code 101)",
                    probable_causes=("Cooling failure",),
                    checks=("Do not reset until the cooling fault is fixed",),
                ),
            ),
        ),
        PointGuide(
            site_id=site_id,
            device_id=device.device_id,
            point_name=alarms,
            meaning=f"{prefix}'s alarm word: each set bit is an active alarm.",
            unit_note="Bit 0 is the least significant bit.",
            related_points=(status, fault),
            updated_at=_UPDATED,
            author="field engineer (fictional)",
            states=(
                StateGuide(
                    kind=StateKind.BIT,
                    code=0,
                    label="GROUND_FAULT",
                    severity=GuideSeverity.FAULT,
                    message="Insulation fault to ground on the DC side",
                    probable_causes=("Damaged DC cable", "Water in a combiner box"),
                    checks=("Insulation resistance test per string",),
                    safety_note=lockout,
                ),
                StateGuide(
                    kind=StateKind.BIT,
                    code=1,
                    label="DC_OVER_VOLT",
                    severity=GuideSeverity.FAULT,
                    message="DC input voltage too high",
                    probable_causes=("Too many modules per string", "Very cold morning"),
                    checks=("Check the string voltages against the design",),
                ),
                StateGuide(
                    kind=StateKind.BIT,
                    code=2,
                    label="GRID_DISCONNECT",
                    severity=GuideSeverity.FAULT,
                    message="Disconnected from the grid by grid protection",
                    probable_causes=("Grid voltage or frequency out of range",),
                    checks=("Check POI.Frequency and POI.VoltageAB at the event time",),
                    related_points=("POI.Frequency", "POI.VoltageAB"),
                ),
                StateGuide(
                    kind=StateKind.BIT,
                    code=3,
                    label="CABINET_OPEN",
                    severity=GuideSeverity.WARNING,
                    message="Cabinet door is open",
                    checks=("Confirm with the site team whether work is in progress",),
                ),
                StateGuide(
                    kind=StateKind.BIT,
                    code=4,
                    label="OVER_TEMP",
                    severity=GuideSeverity.WARNING,
                    message=f"Cabinet temperature at or above {DERATE_AT_C:g} degC",
                    probable_causes=cooling_causes,
                    checks=cooling_checks,
                    related_points=(temp, status),
                ),
                StateGuide(
                    kind=StateKind.BIT,
                    code=5,
                    label="FAN_FAULT",
                    severity=GuideSeverity.WARNING,
                    message="Cabinet fan fault detected",
                    checks=("Check the fan breaker and the fan itself",),
                    related_points=(temp,),
                ),
            ),
        ),
        PointGuide(
            site_id=site_id,
            device_id=device.device_id,
            point_name=fault,
            meaning=f"{prefix}'s vendor fault code. 0 means no fault.",
            related_points=(status, alarms),
            updated_at=_UPDATED,
            author="field engineer (fictional)",
            states=(
                StateGuide(
                    kind=StateKind.FAULT_CODE,
                    code=101,
                    label="CABINET_OVER_TEMP_TRIP",
                    severity=GuideSeverity.FAULT,
                    message=f"Cabinet temperature reached {TRIP_AT_C:g} degC; stopped",
                    probable_causes=cooling_causes,
                    checks=("Fix cooling first", "Then reset from the local HMI"),
                    related_points=(temp,),
                    safety_note=lockout,
                ),
                StateGuide(
                    kind=StateKind.FAULT_CODE,
                    code=102,
                    label="DC_INSULATION",
                    severity=GuideSeverity.FAULT,
                    message="DC insulation resistance below limit",
                    checks=("Insulation resistance test per string",),
                    safety_note=lockout,
                ),
                StateGuide(
                    kind=StateKind.FAULT_CODE,
                    code=103,
                    label="GRID_OUT_OF_RANGE",
                    severity=GuideSeverity.FAULT,
                    message="Grid voltage or frequency outside the ride-through limits",
                    related_points=("POI.Frequency", "POI.VoltageAB"),
                ),
                StateGuide(
                    kind=StateKind.FAULT_CODE,
                    code=104,
                    label="FAN_FAILURE",
                    severity=GuideSeverity.FAULT,
                    message="Cabinet fan failed",
                    checks=("Replace the fan",),
                    safety_note=lockout,
                ),
            ),
        ),
    )


# --- Sunfield (site 1) -----------------------------------------------------------------------

_INV1 = Device(
    device_id=10,
    name="INV1",
    type="INVERTER",
    vendor="Fictional Power",
    model="FP-2500C",
    description="2.5 MW central inverter, PV field A",
)
_INV2 = Device(
    device_id=11,
    name="INV2",
    type="INVERTER",
    vendor="Fictional Power",
    model="FP-2500C",
    description="2.5 MW central inverter, PV field B",
)
_BESS1 = Device(
    device_id=20,
    name="BESS1",
    type="BESS",
    vendor="Fictional Storage",
    model="FS-2000",
    description="2 MW / 4 MWh battery",
)
_POI1 = Device(
    device_id=30,
    name="POI",
    type="METER",
    vendor="Fictional Meters",
    model="FM-300",
    description="Revenue meter at the 20 kV point of interconnection",
)
_WS1 = Device(
    device_id=40,
    name="WS1",
    type="IED",
    vendor="Fictional Sensors",
    model="WX-1",
    description="Weather station",
)

SUNFIELD = FakeSite(
    site=Site(
        site_id=1,
        name="Sunfield Demo (PV + BESS)",
        description="Fictional 5 MW PV plant with a 2 MW / 4 MWh battery, for development.",
        capacity_kw=5000,
        timezone="Europe/Berlin",
        latitude=48.10,
        longitude=11.50,
    ),
    devices=(_INV1, _INV2, _BESS1, _POI1, _WS1),
    topology=Topology(
        nodes=(
            TopologyNode(node_id="grid", type="grid", name="20 kV grid"),
            TopologyNode(node_id="poi", type="meter", name="POI meter", device_id=30),
            TopologyNode(node_id="tx1", type="transformer", name="TX1 20/0.6 kV"),
            TopologyNode(node_id="inv1", type="inverter", name="INV1", device_id=10),
            TopologyNode(node_id="inv2", type="inverter", name="INV2", device_id=11),
            TopologyNode(node_id="bess1", type="bess", name="BESS1", device_id=20),
            TopologyNode(node_id="pv_a", type="pv", name="PV field A"),
            TopologyNode(node_id="pv_b", type="pv", name="PV field B"),
            TopologyNode(node_id="ws1", type="met_station", name="WS1", device_id=40),
        ),
        connections=(
            TopologyConnection(from_id="grid", to_id="poi"),
            TopologyConnection(from_id="poi", to_id="tx1"),
            TopologyConnection(from_id="tx1", to_id="inv1"),
            TopologyConnection(from_id="tx1", to_id="inv2"),
            TopologyConnection(from_id="tx1", to_id="bess1"),
            TopologyConnection(from_id="pv_a", to_id="inv1"),
            TopologyConnection(from_id="pv_b", to_id="inv2"),
        ),
    ),
    points=(
        *_inverter_points(_INV1, temp_base=42),
        # INV2 runs about 15 degC hotter (a cooling problem): derated from late morning.
        *_inverter_points(_INV2, temp_base=57),
        _point(
            "BESS1.SOC",
            "Battery state of charge",
            "%",
            _BESS1,
            "battery",
            Signal(
                shape=SignalShape.DAILY_SINE, base=55, amplitude=35, phase_hours=_SOLAR_PHASE - 3
            ),
        ),
        # Charges from the midday PV surplus, discharges overnight.
        _point(
            "BESS1.ActivePower",
            "Battery AC power (+ discharge, - charge)",
            "kW",
            _BESS1,
            "battery",
            Signal(shape=SignalShape.DAILY_SINE, amplitude=-1500, phase_hours=3),
        ),
        _point(
            "BESS1.State",
            "Battery operating state",
            None,
            _BESS1,
            "battery",
            Signal(shape=SignalShape.BESS_STATE, source="BESS1.ActivePower"),
            point_class=PointClass.BINARY,
            data_type="enum16",
            enum_labels=BESS_STATES,
        ),
        _point(
            "POI.ActivePower",
            "Active power at the point of interconnection",
            "kW",
            _POI1,
            "meter",
            Signal(
                shape=SignalShape.SUM,
                base=0.98,
                sources=("INV1.ActivePower", "INV2.ActivePower", "BESS1.ActivePower"),
            ),
        ),
        _point(
            "POI.Frequency",
            "Grid frequency at the POI",
            "Hz",
            _POI1,
            "meter",
            Signal(shape=SignalShape.STEADY, base=50.0, amplitude=0.03),
        ),
        _point(
            "POI.VoltageAB",
            "Line voltage A-B at the POI",
            "kV",
            _POI1,
            "meter",
            Signal(shape=SignalShape.STEADY, base=20.1, amplitude=0.15),
        ),
        _point(
            "WS1.Irradiance",
            "Plane-of-array irradiance",
            "W/m2",
            _WS1,
            "weather_station",
            Signal(shape=SignalShape.SOLAR, amplitude=950, phase_hours=_SOLAR_PHASE),
        ),
        _point(
            "WS1.AmbientTemp",
            "Ambient air temperature",
            "degC",
            _WS1,
            "weather_station",
            Signal(shape=SignalShape.DAILY_SINE, base=17, amplitude=6, phase_hours=_SOLAR_PHASE),
        ),
    ),
    alarm_rules=(
        AlarmRule(
            name="INV1 over-temperature",
            severity=AlarmSeverity.WARNING,
            message="INV1 cabinet over temperature: derating",
            device_id=10,
            point="INV1.AlarmWord",
            bit=4,
        ),
        AlarmRule(
            name="INV2 over-temperature",
            severity=AlarmSeverity.WARNING,
            message="INV2 cabinet over temperature: derating",
            device_id=11,
            point="INV2.AlarmWord",
            bit=4,
        ),
        AlarmRule(
            name="INV2 tripped",
            severity=AlarmSeverity.FAULT,
            message="INV2 tripped: see INV2.FaultCode",
            device_id=11,
            point="INV2.FaultCode",
            at_or_above=1,
        ),
    ),
    static_events=(
        StaticAlarmEvent(
            name="WS1 communication lost",
            severity=AlarmSeverity.FAULT,
            message="No data from WS1 for 10 minutes",
            device_id=40,
            raised_hours_ago=51,
            duration_hours=0.7,
        ),
    ),
    documents=(
        KnowledgeDocument(
            site_id=1,
            kind=KnowledgeKind.MANUAL,
            title="Sunfield operations manual (excerpt)",
            updated_at=_UPDATED,
            body=(
                "Plant layout: two central inverters (INV1, INV2, 2.5 MW each) feed TX1 and the "
                "20 kV POI meter. BESS1 (2 MW / 4 MWh) shares TX1.\n"
                "Inverter states: 0=OFF, 1=SLEEPING, 3=RUNNING, 4=DERATED, 6=FAULT.\n"
                "Inverters derate to about 1500 kW at or above 60 degC cabinet temperature and "
                "trip (fault code 101) at or above 75 degC.\n"
                "Export limit at the POI: 4.5 MW. BESS charges from PV surplus and discharges in "
                "the evening peak (17:00-21:00 local).\n"
                "Normal POI frequency band: 49.9-50.1 Hz. Normal POI voltage: 19.6-20.6 kV."
            ),
        ),
        *(
            KnowledgeDocument(
                site_id=1,
                kind=KnowledgeKind.IM_SCRIPT,
                device_id=device.device_id,
                title=f"{device.name} information model script",
                updated_at=_UPDATED,
                body=(
                    f"device {device.name} type=inverter protocol=modbus-tcp "
                    f"unit={device.device_id - 9}\n"
                    f"map 30001 u32 scale=0.1 -> {device.name}.ActivePower kW\n"
                    f"map 30010 i16 scale=0.1 -> {device.name}.CabinetTemp degC\n"
                    f"map 30020 u16 enum{{0:OFF,1:SLEEPING,3:RUNNING,4:DERATED,6:FAULT}} -> "
                    f"{device.name}.Status\n"
                    f"map 30021 u16 bits{{0:GROUND_FAULT,1:DC_OVER_VOLT,2:GRID_DISCONNECT,"
                    f"3:CABINET_OPEN,4:OVER_TEMP,5:FAN_FAULT}} -> {device.name}.AlarmWord\n"
                    f"map 30022 u16 -> {device.name}.FaultCode\n"
                    "poll every 5s"
                ),
            )
            for device in (_INV1, _INV2)
        ),
        KnowledgeDocument(
            site_id=1,
            kind=KnowledgeKind.IM_SCRIPT,
            device_id=20,
            title="BESS1 information model script",
            updated_at=_UPDATED,
            body=(
                "device BESS1 type=battery protocol=modbus-tcp unit=10\n"
                "map 40001 u16 scale=0.1 -> BESS1.SOC %\n"
                "map 40005 i32 scale=0.1 -> BESS1.ActivePower kW  # + discharge, - charge\n"
                "map 40010 u16 enum{1:STANDBY,2:CHARGING,3:DISCHARGING,99:FAULT} -> BESS1.State\n"
                "poll every 2s"
            ),
        ),
        KnowledgeDocument(
            site_id=1,
            kind=KnowledgeKind.EXPERIENCE_NOTE,
            title="INV2 derating on warm days",
            author="field engineer (fictional)",
            device_id=11,
            point_names=("INV2.CabinetTemp", "INV2.Status", "INV2.AlarmWord"),
            updated_at=_UPDATED,
            body=(
                "INV2 derates on warm days because its cabinet runs about 15 degC hotter than "
                "INV1. Root cause last time: clogged intake filter and a failing cabinet fan. "
                "Check: compare INV2.CabinetTemp with INV1.CabinetTemp; if the gap is above 10 "
                "degC, schedule filter cleaning and a fan inspection."
            ),
        ),
        KnowledgeDocument(
            site_id=1,
            kind=KnowledgeKind.EXPERIENCE_NOTE,
            title="POI voltage high at midday",
            author="grid engineer (fictional)",
            device_id=30,
            point_names=("POI.VoltageAB",),
            updated_at=_UPDATED,
            body=(
                "POI voltage can approach 20.6 kV at midday with full export. The grid operator "
                "accepts it, but if it exceeds 20.6 kV, check the reactive power setpoint "
                "before reducing active power."
            ),
        ),
        KnowledgeDocument(
            site_id=1,
            kind=KnowledgeKind.EXPERIENCE_NOTE,
            title="BESS SOC drift",
            author="field engineer (fictional)",
            device_id=20,
            point_names=("BESS1.SOC",),
            updated_at=_UPDATED,
            body=(
                "BESS1 SOC reading drifts by a few percent over weeks. A full charge cycle "
                "recalibrates it. Do not trust SOC within 3% of the limits without a recent "
                "full cycle."
            ),
        ),
        KnowledgeDocument(
            site_id=1,
            kind=KnowledgeKind.EXPERIENCE_NOTE,
            title="WS1 drops off the network",
            author="SCADA engineer (fictional)",
            device_id=40,
            updated_at=_UPDATED,
            body=(
                "WS1 occasionally stops reporting for under an hour after a firmware watchdog "
                "reset. It recovers on its own; if it stays offline, power-cycle the logger."
            ),
        ),
    ),
    guides=(
        *_inverter_guides(1, _INV1),
        *_inverter_guides(1, _INV2),
        PointGuide(
            site_id=1,
            device_id=20,
            point_name="BESS1.SOC",
            meaning="Battery state of charge as estimated by the BMS.",
            normal_range=NormalRange(min=10, max=95, note="Cycles daily: charged by midday PV"),
            related_points=("BESS1.ActivePower", "BESS1.State"),
            updated_at=_UPDATED,
            author="field engineer (fictional)",
            limits=(
                LimitGuide(
                    condition=LimitCondition.BELOW,
                    value=10,
                    severity=GuideSeverity.WARNING,
                    message="SOC low: discharge will stop soon",
                    checks=("Check the charging schedule", "Check for SOC drift"),
                ),
                LimitGuide(
                    condition=LimitCondition.ABOVE,
                    value=95,
                    severity=GuideSeverity.WARNING,
                    message="SOC high: charging will stop",
                    checks=("Check that PV surplus is not being curtailed unnecessarily",),
                ),
            ),
        ),
        PointGuide(
            site_id=1,
            device_id=20,
            point_name="BESS1.State",
            meaning="Battery operating state reported by the power conversion system.",
            related_points=("BESS1.ActivePower", "BESS1.SOC"),
            updated_at=_UPDATED,
            author="field engineer (fictional)",
            states=(
                StateGuide(
                    kind=StateKind.ENUM_VALUE,
                    code=1,
                    label="STANDBY",
                    severity=GuideSeverity.INFO,
                    message="Idle, ready to run",
                ),
                StateGuide(
                    kind=StateKind.ENUM_VALUE,
                    code=2,
                    label="CHARGING",
                    severity=GuideSeverity.INFO,
                    message="Charging",
                ),
                StateGuide(
                    kind=StateKind.ENUM_VALUE,
                    code=3,
                    label="DISCHARGING",
                    severity=GuideSeverity.INFO,
                    message="Discharging",
                ),
                StateGuide(
                    kind=StateKind.ENUM_VALUE,
                    code=99,
                    label="FAULT",
                    severity=GuideSeverity.FAULT,
                    message="BESS1 stopped on a fault",
                    checks=("Read the BMS and PCS alarm lists on the local HMI",),
                    safety_note="Follow the battery room entry procedure.",
                ),
            ),
        ),
    ),
)

# --- Windridge (site 2) ----------------------------------------------------------------------

_WTG1 = Device(
    device_id=100,
    name="WTG1",
    type="GENERATOR",
    vendor="Fictional Wind",
    model="FW-3000",
    description="3 MW wind turbine",
)
_WTG2 = Device(
    device_id=101,
    name="WTG2",
    type="GENERATOR",
    vendor="Fictional Wind",
    model="FW-3000",
    description="3 MW wind turbine",
)
_POI2 = Device(
    device_id=110,
    name="POI",
    type="METER",
    vendor="Fictional Meters",
    model="FM-300",
    description="Meter at the point of interconnection",
)


def _turbine_points(device: Device, base_kw: float) -> tuple[FakePoint, ...]:
    prefix = device.name
    return (
        _point(
            f"{prefix}.ActivePower",
            f"{prefix} active power",
            "kW",
            device,
            "wind_turbine",
            Signal(shape=SignalShape.DAILY_SINE, base=base_kw, amplitude=900),
        ),
        _point(
            f"{prefix}.WindSpeed",
            f"{prefix} nacelle wind speed",
            "m/s",
            device,
            "wind_turbine",
            Signal(shape=SignalShape.DAILY_SINE, base=9, amplitude=3),
        ),
        _point(
            f"{prefix}.Status",
            f"{prefix} operating state",
            None,
            device,
            "wind_turbine",
            Signal(shape=SignalShape.CONSTANT, base=1),
            point_class=PointClass.BINARY,
            data_type="enum16",
            enum_labels=TURBINE_STATES,
        ),
    )


WINDRIDGE = FakeSite(
    site=Site(
        site_id=2,
        name="Windridge Demo (wind)",
        description="Fictional 6 MW wind farm with two turbines, for development.",
        capacity_kw=6000,
        timezone="Europe/Berlin",
        latitude=53.50,
        longitude=8.10,
    ),
    devices=(_WTG1, _WTG2, _POI2),
    topology=Topology(
        nodes=(
            TopologyNode(node_id="grid", type="grid", name="30 kV grid"),
            TopologyNode(node_id="poi", type="meter", name="POI meter", device_id=110),
            TopologyNode(node_id="wtg1", type="wind", name="WTG1", device_id=100),
            TopologyNode(node_id="wtg2", type="wind", name="WTG2", device_id=101),
        ),
        connections=(
            TopologyConnection(from_id="grid", to_id="poi"),
            TopologyConnection(from_id="poi", to_id="wtg1"),
            TopologyConnection(from_id="poi", to_id="wtg2"),
        ),
    ),
    points=(
        *_turbine_points(_WTG1, base_kw=1800),
        *_turbine_points(_WTG2, base_kw=1750),
        _point(
            "POI.ActivePower",
            "Active power at the point of interconnection",
            "kW",
            _POI2,
            "meter",
            Signal(
                shape=SignalShape.SUM, base=0.98, sources=("WTG1.ActivePower", "WTG2.ActivePower")
            ),
        ),
    ),
    static_events=(
        StaticAlarmEvent(
            name="WTG2 communication lost",
            severity=AlarmSeverity.FAULT,
            message="No data from WTG2 for 10 minutes",
            device_id=101,
            raised_hours_ago=2.8,
            duration_hours=None,
        ),
    ),
    stale_devices={101: 3.0},
    documents=(
        KnowledgeDocument(
            site_id=2,
            kind=KnowledgeKind.MANUAL,
            title="Windridge operations manual (excerpt)",
            updated_at=_UPDATED,
            body="Two 3 MW turbines (WTG1, WTG2). Cut-in 3 m/s, rated 12 m/s, cut-out 25 m/s.",
        ),
        KnowledgeDocument(
            site_id=2,
            kind=KnowledgeKind.EXPERIENCE_NOTE,
            title="WTG2 yaw misalignment",
            author="field engineer (fictional)",
            device_id=101,
            updated_at=_UPDATED,
            body=(
                "WTG2 produced about 3% less than WTG1 at the same wind speed after the yaw "
                "encoder was replaced. Re-run the yaw calibration if the gap returns."
            ),
        ),
        KnowledgeDocument(
            site_id=2,
            kind=KnowledgeKind.EXPERIENCE_NOTE,
            title="WTG2 communication drops",
            author="SCADA engineer (fictional)",
            device_id=101,
            updated_at=_UPDATED,
            body=(
                "WTG2's fibre media converter in the tower base overheats in summer and drops "
                "the link. The turbine keeps running. Power-cycle the converter; replace it if "
                "the drop repeats within a week."
            ),
        ),
    ),
)

FAKE_SITES: tuple[FakeSite, ...] = (SUNFIELD, WINDRIDGE)
