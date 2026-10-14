"""Built-in event scenarios: one library played on the default sites (each has bess1, pv1, load1
and a POI), synced to them at every start as category `default` (read-only).

Each has what it does (`description`) and the expected points:
the point-standard registers it impacts and the values they read, step by step (steps count from
the scenario's start, like the triggers). A test plays every one and checks them, so they stay
true to the simulator. Auto-restore windows only claim what holds for any draw in 2-10 min.
"""

from powerflow.conditions.fault_catalog import FaultCause
from powerflow.conditions.models import (
    AlarmResetChange,
    AssetFaultChange,
    BreakerChange,
    CommLossChange,
    CommTarget,
    ConditionChange,
    GridFrequencyChange,
    GridVoltageChange,
)
from powerflow.conditions.scenario import EventScenario, ExpectedPoint, ScenarioEvent, StepTrigger

BESS, PV, LOAD = "bess.bess1", "pv.pv1", "load.load1"
POI_METER, SITE = "poi_meter.meter", "site.site"


def _at(step: int, change: ConditionChange, label: str) -> ScenarioEvent:
    return ScenarioEvent(at=StepTrigger(step=step), change=change, label=label)


def _fault(asset_id: str, cause: FaultCause, auto_restore: bool = False) -> AssetFaultChange:
    return AssetFaultChange(asset_id=asset_id, cause=cause, auto_restore=auto_restore)


def _clear(asset_id: str) -> AssetFaultChange:
    return AssetFaultChange(asset_id=asset_id, active=False)


def _reset(asset_id: str) -> AlarmResetChange:
    return AlarmResetChange(asset_id=asset_id)


def _expect(
    device: str,
    point: str,
    steps: tuple[int, int],
    equals: float | str | None = None,
    bits_set: tuple[str, ...] = (),
    bits_clear: tuple[str, ...] = (),
    tolerance: float = 0.0,
    note: str | None = None,
) -> ExpectedPoint:
    return ExpectedPoint(
        device=device,
        point=point,
        equals=equals,
        tolerance=tolerance,
        bits_set=list(bits_set),
        bits_clear=list(bits_clear),
        from_step=steps[0],
        to_step=steps[1],
        note=note,
    )


def _tripped(device: str, steps: tuple[int, int]) -> list[ExpectedPoint]:
    """A tripped inverter: FAULT, disconnected, no power."""
    points = [
        _expect(device, "InvSt", steps, equals="FAULT"),
        _expect(device, "ConnSt", steps, equals="DISCONNECTED"),
        _expect(device, "W", steps, equals=0),
    ]
    if device.startswith("bess."):
        points.append(_expect(device, "State", steps, equals="FAULT"))
    return points


BUILTIN_SCENARIOS: dict[str, EventScenario] = {
    "bess1-over-temperature-latched": EventScenario(
        description="BESS 1 trips on over-temperature at step 5; the cause clears at step 60; an "
        "alarm reset at step 90.",
        events=[
            _at(5, _fault("bess1", FaultCause.OVER_TEMPERATURE), "over-temperature trip"),
            _at(60, _clear("bess1"), "cause clears (latched)"),
            _at(90, _reset("bess1"), "alarm reset"),
        ],
        expected_points=[
            *_tripped(BESS, (5, 89)),
            _expect(BESS, "Alrm", (5, 89), bits_set=("OVER_TEMP",)),
            _expect(
                BESS,
                "Evt1",
                (5, 89),
                bits_set=("OVER_TEMP_ALARM",),
                bits_clear=("OVER_TEMP_WARNING",),
            ),
            _expect(BESS, "State", (90, 95), equals="CONNECTED", note="after the reset"),
            _expect(BESS, "Alrm", (90, 95), bits_clear=("OVER_TEMP",)),
            _expect(BESS, "Evt1", (90, 95), bits_clear=("OVER_TEMP_ALARM",)),
        ],
    ),
    "bess1-fan-then-over-temperature": EventScenario(
        description="BESS 1 loses a fan at step 5 (a warning), trips on over-temperature with "
        "auto-restore at step 30, and the fan is repaired at step 700.",
        events=[
            _at(5, _fault("bess1", FaultCause.FAN_ERROR), "fan error (derate 70%)"),
            _at(
                30,
                _fault("bess1", FaultCause.OVER_TEMPERATURE, auto_restore=True),
                "over-temperature trip, auto-restore",
            ),
            _at(700, _clear("bess1"), "fan repaired"),
        ],
        expected_points=[
            _expect(BESS, "State", (5, 29), equals="CONNECTED", note="warning: still running"),
            _expect(BESS, "Evt1", (5, 29), bits_set=("FAN_ERROR",)),
            _expect(BESS, "ThrotSrc", (5, 29), bits_set=("DERATED",)),
            *_tripped(BESS, (30, 148)),
            _expect(BESS, "Evt1", (30, 148), bits_set=("OVER_TEMP_ALARM", "FAN_ERROR")),
            _expect(BESS, "State", (630, 699), equals="CONNECTED", note="auto-restored"),
            _expect(
                BESS,
                "Evt1",
                (630, 699),
                bits_set=("FAN_ERROR",),
                bits_clear=("OVER_TEMP_ALARM",),
            ),
            _expect(BESS, "Evt1", (700, 705), bits_clear=("FAN_ERROR",)),
            _expect(BESS, "ThrotSrc", (700, 705), bits_clear=("DERATED",)),
        ],
    ),
    "pv1-ground-fault-auto-restore": EventScenario(
        description="PV 1 trips on a ground fault at step 5, injected with auto-restore.",
        events=[
            _at(5, _fault("pv1", FaultCause.GROUND_FAULT, auto_restore=True), "ground fault"),
        ],
        expected_points=[
            *_tripped(PV, (5, 123)),
            _expect(PV, "Alrm", (5, 123), bits_set=("GROUND_FAULT",)),
            _expect(PV, "FltCode", (5, 123), equals=101),
            _expect(SITE, "NInvFlt", (5, 123), equals=1),
            _expect(PV, "ConnSt", (605, 610), equals="CONNECTED", note="auto-restored"),
            _expect(PV, "Alrm", (605, 610), bits_clear=("GROUND_FAULT",)),
            _expect(PV, "FltCode", (605, 610), equals=0),
            _expect(SITE, "NInvFlt", (605, 610), equals=0),
        ],
    ),
    "pv1-blown-string-fuse": EventScenario(
        description="A PV 1 string fuse blows at step 5 (a warning); it's replaced at step 120.",
        events=[
            _at(5, _fault("pv1", FaultCause.BLOWN_STRING_FUSE), "string fuse blows"),
            _at(120, _clear("pv1"), "fuse replaced"),
        ],
        expected_points=[
            _expect(PV, "ConnSt", (5, 119), equals="CONNECTED", note="warning: still running"),
            _expect(PV, "Alrm", (5, 119), bits_set=("BLOWN_STRING_FUSE",)),
            _expect(PV, "ThrotSrc", (5, 119), bits_set=("DERATED",)),
            _expect(PV, "FltCode", (5, 119), equals=0),
            _expect(PV, "Alrm", (120, 125), bits_clear=("BLOWN_STRING_FUSE",)),
            _expect(PV, "ThrotSrc", (120, 125), bits_clear=("DERATED",)),
        ],
    ),
    "door-open-and-emergency-stop": EventScenario(
        description="BESS 1's cabinet door opens and PV 1 is emergency-stopped at step 5; both "
        "causes clear at step 30; both get an alarm reset at step 60.",
        events=[
            _at(5, _fault("bess1", FaultCause.DOOR_OPEN), "BESS 1 door open"),
            _at(5, _fault("pv1", FaultCause.EMERGENCY_STOP), "PV 1 e-stop"),
            _at(30, _clear("bess1"), "door closed (latched)"),
            _at(30, _clear("pv1"), "e-stop released (latched)"),
            _at(60, _reset("bess1"), "BESS 1 alarm reset"),
            _at(60, _reset("pv1"), "PV 1 alarm reset"),
        ],
        expected_points=[
            *_tripped(BESS, (5, 59)),
            _expect(BESS, "Alrm", (5, 59), bits_set=("CABINET_OPEN",)),
            _expect(BESS, "Evt1", (5, 59), bits_set=("OPEN_DOOR_ERROR",)),
            *_tripped(PV, (5, 59)),
            _expect(PV, "Alrm", (5, 59), bits_set=("MANUAL_SHUTDOWN",)),
            _expect(PV, "FltCode", (5, 59), equals=105),
            _expect(BESS, "State", (60, 65), equals="CONNECTED", note="after the reset"),
            _expect(BESS, "Alrm", (60, 65), bits_clear=("CABINET_OPEN",)),
            _expect(PV, "Alrm", (60, 65), bits_clear=("MANUAL_SHUTDOWN",)),
            _expect(PV, "FltCode", (60, 65), equals=0),
        ],
    ),
    "reset-while-fault-active": EventScenario(
        description="BESS 1 trips (generic) at step 5; an alarm reset at step 20 while the cause "
        "is still there; the cause clears at step 40; another reset at step 60.",
        events=[
            _at(5, _fault("bess1", FaultCause.TRIP), "trip"),
            _at(20, _reset("bess1"), "reset: no effect"),
            _at(40, _clear("bess1"), "cause clears (latched)"),
            _at(60, _reset("bess1"), "reset: restores"),
        ],
        expected_points=[
            *_tripped(BESS, (5, 59)),
            _expect(BESS, "Alrm", (5, 59), bits_set=("MANUFACTURER_ALRM",)),
            _expect(BESS, "Evt1", (5, 59), bits_set=("OTHER_ALARM",)),
            _expect(BESS, "State", (60, 65), equals="CONNECTED", note="after the second reset"),
            _expect(BESS, "Alrm", (60, 65), bits_clear=("MANUFACTURER_ALRM",)),
        ],
    ),
    "grid-frequency-excursion": EventScenario(
        description="The grid frequency drops to 59.3 Hz at step 5 and returns to nominal at "
        "step 35.",
        events=[
            _at(5, GridFrequencyChange(hz=59.3), "59.3 Hz"),
            _at(35, GridFrequencyChange(hz=None), "back to nominal"),
        ],
        expected_points=[
            _expect(POI_METER, "Hz", (5, 34), equals=59.3, tolerance=0.03),
            _expect(PV, "Alrm", (5, 34), bits_set=("UNDER_FREQUENCY",)),
            _expect(BESS, "Alrm", (5, 34), bits_set=("UNDER_FREQUENCY",)),
            _expect(POI_METER, "Hz", (35, 40), equals=60.0, tolerance=0.03),
            _expect(PV, "Alrm", (35, 40), bits_clear=("UNDER_FREQUENCY",)),
            _expect(BESS, "Alrm", (35, 40), bits_clear=("UNDER_FREQUENCY",)),
        ],
    ),
    "grid-voltage-sag": EventScenario(
        description="The source voltage sags to 0.9 pu at step 5 and recovers at step 35.",
        events=[
            _at(5, GridVoltageChange(vm_pu=0.9), "sag to 0.9 pu"),
            _at(35, GridVoltageChange(vm_pu=None), "recovered"),
        ],
        expected_points=[
            _expect(BESS, "Alrm", (5, 34), bits_set=("AC_UNDER_VOLT",)),
            _expect(PV, "Alrm", (5, 34), bits_set=("AC_UNDER_VOLT",)),
            _expect(POI_METER, "Evt", (5, 34), bits_set=("M_EVENT_Under_Voltage",)),
            _expect(LOAD, "Alrm", (5, 34), bits_set=("UNDERVOLTAGE",)),
            _expect(BESS, "Alrm", (35, 40), bits_clear=("AC_UNDER_VOLT",)),
            _expect(POI_METER, "Evt", (35, 40), bits_clear=("M_EVENT_Under_Voltage",)),
        ],
    ),
    "poi-trip": EventScenario(
        description="The POI breaker opens at step 5 and recloses at step 35.",
        events=[
            _at(5, BreakerChange(breaker="poi", closed=False), "POI opens"),
            _at(35, BreakerChange(breaker="poi", closed=True), "POI recloses"),
        ],
        expected_points=[
            _expect(SITE, "GridMode", (5, 34), equals="BLACKOUT"),
            _expect(POI_METER, "BrkPos", (5, 34), equals="OPEN"),
            _expect(POI_METER, "Hz", (5, 34), equals=0),
            _expect(BESS, "St", (5, 34), equals="OFF"),
            _expect(BESS, "Alrm", (5, 34), bits_set=("GRID_DISCONNECT",)),
            _expect(PV, "InvSt", (5, 34), equals="OFF"),
            _expect(PV, "Alrm", (5, 34), bits_set=("GRID_DISCONNECT",)),
            _expect(LOAD, "SupplySt", (5, 34), equals="DE_ENERGIZED"),
            _expect(SITE, "GridMode", (35, 40), equals="GRID_TIED"),
            _expect(POI_METER, "BrkPos", (35, 40), equals="CLOSED"),
            _expect(LOAD, "SupplySt", (35, 40), equals="ENERGIZED"),
        ],
    ),
    "bess1-breaker-open": EventScenario(
        description="BESS 1's breaker opens at step 5 and closes at step 35.",
        events=[
            _at(5, BreakerChange(breaker="bess1", closed=False), "BESS 1 breaker opens"),
            _at(35, BreakerChange(breaker="bess1", closed=True), "BESS 1 breaker closes"),
        ],
        expected_points=[
            _expect(BESS, "BrkPos", (5, 34), equals="OPEN"),
            _expect(BESS, "St", (5, 34), equals="OFF"),
            _expect(BESS, "State", (5, 34), equals="DISCONNECTED"),
            _expect(BESS, "Hz", (5, 34), equals=0),
            _expect(BESS, "AuxW", (5, 34), equals=0),
            _expect(BESS, "Alrm", (5, 34), bits_set=("AC_DISCONNECT",)),
            _expect(SITE, "GridMode", (5, 34), equals="GRID_TIED"),
            _expect(BESS, "BrkPos", (35, 40), equals="CLOSED"),
            _expect(BESS, "State", (35, 40), equals="CONNECTED"),
            _expect(BESS, "Alrm", (35, 40), bits_clear=("AC_DISCONNECT",)),
        ],
    ),
    "bess1-comm-loss": EventScenario(
        description="BESS 1 stops updating at step 5; communication returns at step 35.",
        events=[
            _at(5, CommLossChange(target=CommTarget.ASSET, id="bess1"), "BESS 1 comm lost"),
            _at(
                35,
                CommLossChange(target=CommTarget.ASSET, id="bess1", active=False),
                "BESS 1 comm restored",
            ),
        ],
        expected_points=[
            _expect(BESS, "Evt1", (5, 34), bits_set=("COMMUNICATION_ERROR",)),
            _expect(SITE, "Alrm", (5, 34), bits_set=("DEVICE_COMM_LOSS",)),
            _expect(BESS, "Evt1", (35, 40), bits_clear=("COMMUNICATION_ERROR",)),
            _expect(SITE, "Alrm", (35, 40), bits_clear=("DEVICE_COMM_LOSS",)),
        ],
    ),
    "poi-meter-comm-loss": EventScenario(
        description="The POI meter stops updating at step 5; communication returns at step 35.",
        events=[
            _at(5, CommLossChange(target=CommTarget.POI_METER), "POI meter comm lost"),
            _at(
                35,
                CommLossChange(target=CommTarget.POI_METER, active=False),
                "POI meter comm restored",
            ),
        ],
        expected_points=[
            _expect(SITE, "Alrm", (5, 34), bits_set=("POI_METER_FAIL",)),
            _expect(SITE, "Alrm", (35, 40), bits_clear=("POI_METER_FAIL",)),
        ],
    ),
}
