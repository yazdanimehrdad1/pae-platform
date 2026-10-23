"""Site data shapes (sites, devices, topology, points, readings, alarms, comms). They mirror
what backend-ot serves; the fake and backend-ot connectors both map onto them."""

from datetime import datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

# --- Site data --------------------------------------------------------------------------------


class Site(BaseModel):
    model_config = ConfigDict(frozen=True)

    site_id: int
    name: str
    description: str | None = None
    capacity_kw: float | None = None
    timezone: str = "UTC"
    latitude: float | None = None
    longitude: float | None = None


class Device(BaseModel):
    model_config = ConfigDict(frozen=True)

    device_id: int
    name: str
    type: str  # backend-ot device type: INVERTER, BESS, METER, ...
    vendor: str | None = None
    model: str | None = None
    description: str | None = None


class TopologyNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str
    type: str  # grid, poi, meter, transformer, breaker, pv, inverter, bess, ...
    name: str
    device_id: int | None = None


class TopologyConnection(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_id: str
    to_id: str


class Topology(BaseModel):
    """The single-line diagram, condensed: what is connected to what."""

    model_config = ConfigDict(frozen=True)

    nodes: tuple[TopologyNode, ...] = ()
    connections: tuple[TopologyConnection, ...] = ()


class PointClass(StrEnum):
    ANALOG = "ANALOG"  # metered or continuous values
    BINARY = "BINARY"  # state, status, flags
    ALARM = "ALARM"  # warning, fault, error, trip
    CONTROL = "CONTROL"  # setpoint, command, configuration


class PointInfo(BaseModel):
    """One data point (tag) in a site's catalog. `name` is unique within a site."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str | None = None
    unit: str | None = None
    device_id: int
    device_name: str
    equipment: str
    data_type: str = "float32"
    point_class: PointClass | None = None
    # backend-ot point severity (HIGH | MEDIUM | LOW), mostly set on ALARM-class points.
    severity: str | None = None
    # Value -> label for enum points; bit index (0 = LSB) -> label for bitfield points.
    enum_labels: dict[int, str] = Field(default_factory=dict[int, str])
    bit_labels: dict[int, str] = Field(default_factory=dict[int, str])


class PointValue(BaseModel):
    name: str
    device_id: int
    value: float | int | str | bool | None
    unit: str | None = None
    # None: the point has never been read.
    timestamp: AwareDatetime | None = None
    quality: str | None = None
    # Enum points: the label of the current value. Bitfield points: the labels of the set bits.
    label: str | None = None
    active_bits: list[str] | None = None
    age_s: float | None = None
    # No new reading for longer than the stale threshold: the device may have stopped reporting.
    stale: bool = False


class HistorySample(BaseModel):
    timestamp: datetime
    value: float


class StateChange(BaseModel):
    """A change of an enum or bitfield point's value (the first entry is the value at start)."""

    timestamp: datetime
    value: int
    label: str | None = None
    active_bits: list[str] | None = None


class AlarmSeverity(StrEnum):
    FAULT = "fault"
    WARNING = "warning"


class AlarmEvent(BaseModel):
    alarm_name: str
    severity: AlarmSeverity
    message: str
    device_id: int | None = None  # None: a site-level alarm
    raised_at: AwareDatetime
    cleared_at: AwareDatetime | None = None  # None: still active


class ActivePointAlarm(BaseModel):
    """An ALARM-class point whose latest value is non-zero (a fault/warning word, a fault code)."""

    point_name: str
    device_id: int
    severity: str | None = None
    value: float | int
    label: str | None = None
    active_bits: list[str] | None = None
    timestamp: AwareDatetime


class ActiveAlarms(BaseModel):
    events: list[AlarmEvent]
    point_alarms: list[ActivePointAlarm]


class DeviceComms(BaseModel):
    device_id: int
    last_reading_at: AwareDatetime | None
    stale: bool


# --- Engineer knowledge ---------------------------------------------------------------------
