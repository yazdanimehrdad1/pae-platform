"""Shapes of the fake data: signals of the plant model, alarm rules, and a fake site."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from intelli_gateway.schemas.knowledge import KnowledgeDocument, PointGuide
from intelli_gateway.schemas.site_data import AlarmSeverity, Device, PointInfo, Site, Topology


class SignalShape(StrEnum):
    SOLAR = "solar"  # bell curve over daylight hours, zero at night
    DAILY_SINE = "daily_sine"  # base + amplitude * sine with a 24 h period, peak mid-afternoon
    STEADY = "steady"  # base + a small fast wobble
    CONSTANT = "constant"  # base
    SUM = "sum"  # base-scaled sum of `sources`
    INVERTER_STATUS = "inverter_status"  # from daylight and the temperature in `source`
    INVERTER_POWER = "inverter_power"  # solar output limited by the status in `source`
    ALARM_WORD = "alarm_word"  # bits set by `bit_rules`
    FAULT_CODE = "fault_code"  # `code` while the status in `source` equals `threshold`
    BESS_STATE = "bess_state"  # from the sign of the power in `source`


class BitRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    bit: int
    point: str
    at_or_above: float


class Signal(BaseModel):
    model_config = ConfigDict(frozen=True)

    shape: SignalShape
    base: float = 0.0
    amplitude: float = 0.0
    # Hours added to UTC before applying the daily shape (rough local solar time).
    phase_hours: float = 0.0
    source: str | None = None
    sources: tuple[str, ...] = ()
    threshold: float = 0.0
    trip: float = 0.0
    limit: float = 0.0
    code: int = 0
    bit_rules: tuple[BitRule, ...] = ()


class FakePoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    info: PointInfo
    signal: Signal


class AlarmRule(BaseModel):
    """Raised while the bit is set (or the value is at or above `at_or_above`)."""

    model_config = ConfigDict(frozen=True)

    name: str
    severity: AlarmSeverity
    message: str
    device_id: int | None
    point: str
    bit: int | None = None
    at_or_above: float | None = None


class StaticAlarmEvent(BaseModel):
    """A one-off event placed relative to now (e.g. a comms loss three hours ago)."""

    model_config = ConfigDict(frozen=True)

    name: str
    severity: AlarmSeverity
    message: str
    device_id: int | None
    raised_hours_ago: float
    duration_hours: float | None  # None: still active


class FakeSite(BaseModel):
    model_config = ConfigDict(frozen=True)

    site: Site
    devices: tuple[Device, ...]
    topology: Topology
    points: tuple[FakePoint, ...]
    alarm_rules: tuple[AlarmRule, ...] = ()
    static_events: tuple[StaticAlarmEvent, ...] = ()
    # Devices that stopped reporting, and how many hours ago.
    stale_devices: dict[int, float] = {}
    documents: tuple[KnowledgeDocument, ...] = ()
    guides: tuple[PointGuide, ...] = ()
