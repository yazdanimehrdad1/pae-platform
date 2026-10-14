"""The fault cause catalog: what each injectable cause does to a BESS or PV inverter.

One row per (asset kind, cause), the single source of truth for the UI (GET /sim/fault-causes),
the point standard (calc.py sets the listed bits) and the tests.

- **fault:** the inverter trips (P = Q = 0, FAULT states) and its bits are set. Clearing the
  injection latches it (FAULT and the bits stay) until an alarm reset, unless it was injected
  with auto-restore (it then clears itself 2-10 min of sim time after injection).
- **warning:** the inverter keeps running, derated, with its warning bits set; clearing it
  removes it at once (warnings don't latch).

Bit values are point-standard symbol names (701.Alrm, 802.Evt1), resolved in point_standard/, so
this module imports nothing from it. The derate factors and PV fault codes are placeholders.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

AssetKind = Literal["bess", "pv"]

# Auto-restore: a fault clears itself this long (sim time, uniform) after injection.
AUTO_RESTORE_MIN_S = 120.0
AUTO_RESTORE_MAX_S = 600.0


class FaultCause(StrEnum):
    TRIP = "trip"  # generic: the vendor's own fault
    OVER_TEMPERATURE = "over_temperature"
    UNDER_TEMPERATURE = "under_temperature"
    GROUND_FAULT = "ground_fault"
    DC_OVERVOLTAGE = "dc_overvoltage"
    DC_UNDERVOLTAGE = "dc_undervoltage"
    OVER_CHARGE_CURRENT = "over_charge_current"
    OVER_DISCHARGE_CURRENT = "over_discharge_current"
    CONTACTOR_ERROR = "contactor_error"
    DOOR_OPEN = "door_open"
    EMERGENCY_STOP = "emergency_stop"
    OVER_TEMPERATURE_WARNING = "over_temperature_warning"
    FAN_ERROR = "fan_error"
    BLOWN_STRING_FUSE = "blown_string_fuse"


class Severity(StrEnum):
    FAULT = "fault"  # trips; latches unless auto-restore
    WARNING = "warning"  # keeps running (derated); never latches


@dataclass(frozen=True)
class CauseSpec:
    kind: AssetKind
    cause: FaultCause
    label: str
    severity: Severity
    alrm: tuple[str, ...] = ()  # 701.Alrm symbols
    evt1: tuple[str, ...] = ()  # 802.Evt1 symbols (BESS only)
    fault_code: int = 0  # PV FltCode (0 = none)
    p_max_factor: float = 1.0  # warnings: the inverter's P/S rating is scaled by this
    p_available_factor: float = 1.0  # warnings: PV available power is scaled by this


FAULT, WARNING = Severity.FAULT, Severity.WARNING
Cause = FaultCause

# In table order: the first active PV fault gives FltCode.
CATALOG: tuple[CauseSpec, ...] = (
    CauseSpec(
        "bess", Cause.TRIP, "Trip (generic)", FAULT, ("MANUFACTURER_ALRM",), ("OTHER_ALARM",)
    ),
    CauseSpec(
        "bess",
        Cause.OVER_TEMPERATURE,
        "Over-temperature",
        FAULT,
        ("OVER_TEMP",),
        ("OVER_TEMP_ALARM",),
    ),
    CauseSpec(
        "bess",
        Cause.UNDER_TEMPERATURE,
        "Under-temperature",
        FAULT,
        ("UNDER_TEMP",),
        ("UNDER_TEMP_ALARM",),
    ),
    CauseSpec(
        "bess", Cause.GROUND_FAULT, "Ground fault", FAULT, ("GROUND_FAULT",), ("GROUND_FAULT",)
    ),
    CauseSpec(
        "bess",
        Cause.DC_OVERVOLTAGE,
        "DC overvoltage",
        FAULT,
        ("DC_OVER_VOLT",),
        ("OVER_VOLT_ALARM",),
    ),
    CauseSpec("bess", Cause.DC_UNDERVOLTAGE, "DC undervoltage", FAULT, (), ("UNDER_VOLT_ALARM",)),
    CauseSpec(
        "bess",
        Cause.OVER_CHARGE_CURRENT,
        "Over charge current",
        FAULT,
        (),
        ("OVER_CHARGE_CURRENT_ALARM",),
    ),
    CauseSpec(
        "bess",
        Cause.OVER_DISCHARGE_CURRENT,
        "Over discharge current",
        FAULT,
        (),
        ("OVER_DISCHARGE_CURRENT_ALARM",),
    ),
    CauseSpec(
        "bess",
        Cause.CONTACTOR_ERROR,
        "DC contactor error",
        FAULT,
        ("DC_DISCONNECT",),
        ("CONTACTOR_ERROR",),
    ),
    CauseSpec(
        "bess", Cause.DOOR_OPEN, "Cabinet door open", FAULT, ("CABINET_OPEN",), ("OPEN_DOOR_ERROR",)
    ),
    CauseSpec("bess", Cause.EMERGENCY_STOP, "Emergency stop", FAULT, ("MANUAL_SHUTDOWN",)),
    CauseSpec(
        "bess",
        Cause.OVER_TEMPERATURE_WARNING,
        "Over-temperature warning",
        WARNING,
        (),
        ("OVER_TEMP_WARNING",),
        p_max_factor=0.5,
    ),
    CauseSpec("bess", Cause.FAN_ERROR, "Fan error", WARNING, (), ("FAN_ERROR",), p_max_factor=0.7),
    CauseSpec("pv", Cause.TRIP, "Trip (generic)", FAULT, ("MANUFACTURER_ALRM",), fault_code=100),
    CauseSpec("pv", Cause.GROUND_FAULT, "Ground fault", FAULT, ("GROUND_FAULT",), fault_code=101),
    CauseSpec(
        "pv", Cause.DC_OVERVOLTAGE, "DC overvoltage", FAULT, ("DC_OVER_VOLT",), fault_code=102
    ),
    CauseSpec(
        "pv", Cause.OVER_TEMPERATURE, "Over-temperature", FAULT, ("OVER_TEMP",), fault_code=103
    ),
    CauseSpec("pv", Cause.DOOR_OPEN, "Cabinet door open", FAULT, ("CABINET_OPEN",), fault_code=104),
    CauseSpec(
        "pv", Cause.EMERGENCY_STOP, "Emergency stop", FAULT, ("MANUAL_SHUTDOWN",), fault_code=105
    ),
    CauseSpec(
        "pv",
        Cause.BLOWN_STRING_FUSE,
        "Blown string fuse",
        WARNING,
        ("BLOWN_STRING_FUSE",),
        p_available_factor=0.9,
    ),
    CauseSpec(
        "pv",
        Cause.OVER_TEMPERATURE_WARNING,
        "Over-temperature warning",
        WARNING,
        ("OVER_TEMP",),
        p_max_factor=0.5,
    ),
)

_SPECS: dict[tuple[AssetKind, FaultCause], CauseSpec] = {
    (spec.kind, spec.cause): spec for spec in CATALOG
}
_ORDER: dict[tuple[AssetKind, FaultCause], int] = {
    (spec.kind, spec.cause): index for index, spec in enumerate(CATALOG)
}
# A cause has the same severity on every asset kind (checked by the tests).
SEVERITY: dict[FaultCause, Severity] = {spec.cause: spec.severity for spec in CATALOG}


def causes_for(kind: AssetKind) -> frozenset[FaultCause]:
    return frozenset(spec.cause for spec in CATALOG if spec.kind == kind)


def cause_spec(kind: AssetKind, cause: FaultCause) -> CauseSpec | None:
    return _SPECS.get((kind, cause))


def catalog_order(kind: AssetKind, cause: FaultCause) -> int:
    return _ORDER.get((kind, cause), len(CATALOG))


class FaultCauseInfo(BaseModel):
    """One injectable cause on one asset kind, and the points it drives."""

    asset_type: AssetKind
    cause: FaultCause
    label: str
    severity: Severity
    alrm: list[str] = Field(description="701.Alrm bits it sets.")
    evt1: list[str] = Field(description="802.Evt1 bits it sets (BESS).")
    fault_code: int = Field(description="PV FltCode while it's the first active fault (0 = none).")
    p_max_factor: float = Field(description="Warnings: the P/S rating is scaled by this.")
    p_available_factor: float = Field(description="Warnings: PV available power is scaled by this.")


def catalog_info() -> list[FaultCauseInfo]:
    return [
        FaultCauseInfo(
            asset_type=spec.kind,
            cause=spec.cause,
            label=spec.label,
            severity=spec.severity,
            alrm=list(spec.alrm),
            evt1=list(spec.evt1),
            fault_code=spec.fault_code,
            p_max_factor=spec.p_max_factor,
            p_available_factor=spec.p_available_factor,
        )
        for spec in CATALOG
    ]
