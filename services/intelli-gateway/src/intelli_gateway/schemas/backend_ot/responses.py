"""backend-ot's response bodies, as far as intelli-gateway reads them.

Strict (`extra="forbid"`), per contracts/README.md: a field backend-ot adds or renames fails
validation instead of being silently ignored. tests/test_backend_ot_contract.py checks every
model here against contracts/openapi/backend-ot.openapi.json, so drift fails `make test`.
Field names and optionality follow that spec exactly.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PointClassName = Literal["ANALOG", "BINARY", "ALARM", "CONTROL"]
PointSeverityName = Literal["HIGH", "MEDIUM", "LOW"]
AlarmSeverityName = Literal["fault", "warning"]
# A translated reading: an enum label, or {bit label: 0 | 1} for a bitfield.
TranslatedValue = str | dict[str, int] | None


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --- sites (GET /api/sites, /api/sites/{site_id}) ---


class Coordinates(StrictModel):
    lat: float
    lng: float
    elevation_m: float | None = None


class Location(StrictModel):
    street: str
    city: str
    state: str
    zip_code: int


class SiteResponse(StrictModel):
    site_id: int
    client_id: str
    name: str
    operator: str
    capacity: str
    device_count: int
    created_at: datetime
    updated_at: datetime
    last_update: datetime
    coordinates: Coordinates | None = None
    deleted_at: datetime | None = None
    description: str | None = None
    location: Location | None = None
    profile: str | None = None
    timezone: str = "UTC"


# --- PV arrays (GET /api/sites/{site_id}/pv-arrays) ---


class PvArrayConfigResponse(StrictModel):
    """The PV array behind a PV or INVERTER device. Azimuth: degrees clockwise from north."""

    device_id: int
    site_id: int
    device_name: str
    device_type: str
    tilt_deg: float
    azimuth_deg: float
    dc_capacity_kw: float
    ac_capacity_kw: float
    system_loss_pct: float
    temp_coefficient_pct_per_c: float
    created_at: datetime
    updated_at: datetime


# --- devices with their points (GET /api/devices/site/{site_id}/devices) ---


class DevicePointResponse(StrictModel):
    id: int
    site_id: int
    device_id: int
    name: str
    address: int
    size: int
    data_type: str
    bitfield_detail: dict[str, str] | None = None
    byte_order: str = "big-endian"
    category: str = "NATIVE"
    point_class: PointClassName | None = Field(default=None, alias="class")
    deleted_at: datetime | None = None
    enum_detail: dict[str, str] | None = None
    poll_kind: str | None = None
    scale_factor: float | None = None
    severity: PointSeverityName | None = None
    source_point_id: int | None = None
    unit: str | None = None
    virtual_definition: dict[str, object] | None = None
    word_order: str = "msw_first"


class DevicePointsCategoryGrouped(StrictModel):
    native: list[DevicePointResponse] = []
    standardized: list[DevicePointResponse] = []
    virtual: list[DevicePointResponse] = []


class RegisterRange(StrictModel):
    start_index: int
    count: int


class DeviceScanRanges(StrictModel):
    coils: list[RegisterRange] = []
    holding: list[RegisterRange] = []
    input: list[RegisterRange] = []


class DeviceWithPoints(StrictModel):
    device_id: int
    site_id: int
    name: str
    type: str
    protocol: str
    host: str
    port: int
    server_address: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    description: str | None = None
    modbus_address_mode: str = "zero_based"
    model: str | None = None
    points: DevicePointsCategoryGrouped = DevicePointsCategoryGrouped()
    poll_enabled: bool = True
    read_from_aggregator: bool = True
    scan_ranges: DeviceScanRanges | None = None
    scan_ranges_locked: bool = False
    timeout: float | None = None
    vendor: str | None = None


# --- readings (GET /api/device-point-readings/...) ---


class LatestMeta(StrictModel):
    site_id: int
    device_id: int
    total_count: int
    point_ids: list[int] | None = None


class PointLatest(StrictModel):
    id: int
    name: str
    data_type: str
    point_class: PointClassName | None = Field(default=None, alias="class")
    severity: PointSeverityName | None = None
    time: datetime | None = None
    translated_value: TranslatedValue = None
    unit: str | None = None
    value: float | None = None


class LatestResponse(StrictModel):
    meta: LatestMeta
    readings: dict[str, PointLatest]


class TimeseriesMeta(StrictModel):
    site_id: int
    device_id: int
    total_count: int
    end_time: datetime | None = None
    point_ids: list[int] | None = None
    start_time: datetime | None = None


class TimeseriesPoint(StrictModel):
    time: datetime
    translated_value: TranslatedValue = None
    value: float | None = None


class PointTimeseries(StrictModel):
    id: int
    name: str
    data_type: str
    bit_labels: list[str] | None = None
    point_class: PointClassName | None = Field(default=None, alias="class")
    count: int = 0
    enum_map: dict[str, str] | None = None
    severity: PointSeverityName | None = None
    timeseries: list[TimeseriesPoint] = []
    unit: str | None = None


class TimeseriesResponse(StrictModel):
    meta: TimeseriesMeta
    readings: dict[str, PointTimeseries]


# --- alarms (GET /api/alarms/site/{site_id}/snapshot, /events) ---


class AlarmDefinitionResponse(StrictModel):
    id: int
    site_id: int
    source: Literal["USER", "PROFILE"]
    name: str
    kind: Literal["threshold", "comms_stale", "condition", "profile"]
    severity: AlarmSeverityName
    message: str
    enabled: bool
    notify_mobile: bool
    notify_email: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    profile_alarm_key: str | None = None
    rule: dict[str, object] | None = None


class AlarmEventResponse(StrictModel):
    id: int
    definition_id: int
    site_id: int
    severity: AlarmSeverityName
    raised_at: datetime
    message: str
    cleared_at: datetime | None = None
    device_id: int | None = None
    value_at_raise: float | None = None


class AlarmLogEntry(StrictModel):
    id: str
    event_id: int
    definition_id: int
    kind: Literal["raised", "cleared"]
    severity: AlarmSeverityName
    at: datetime
    message: str
    device_id: int | None = None


class AlarmSnapshotResponse(StrictModel):
    site_id: int
    now: datetime
    definitions: list[AlarmDefinitionResponse]
    events: list[AlarmEventResponse]
    log: list[AlarmLogEntry]


# --- site health: active ALARM-class points (GET /api/sites/{site_id}/health) ---


class ActivePointAlarm(StrictModel):
    device_point_id: int
    device_point_name: str
    value: float
    timestamp: datetime
    active_bits: list[str] = []
    enum_label: str | None = None
    severity: PointSeverityName | None = None


class DeviceAlarmStatus(StrictModel):
    device_id: int
    device_name: str
    active_alarms: list[ActivePointAlarm] = []
    high_count: int = 0
    highest_severity: PointSeverityName | None = None
    low_count: int = 0
    medium_count: int = 0
    unknown_count: int = 0


class SiteHealthResponse(StrictModel):
    site_id: int
    generated_at: datetime
    device_ids_filter: list[int] | None = None
    devices: list[DeviceAlarmStatus] = []
    high_count: int = 0
    highest_severity: PointSeverityName | None = None
    low_count: int = 0
    medium_count: int = 0
    severity_filter: list[PointSeverityName] | None = None
    unknown_count: int = 0


# --- single-line diagram (GET /api/sites/{site_id}/sld) ---


class SldDeviceLink(StrictModel):
    device_id: int
    points: dict[str, int] = {}


class SldNode(StrictModel):
    id: str
    type: str
    name: str
    col: float
    row: float
    device: SldDeviceLink | None = None
    rating: str | None = None
    voltage: str | None = None


class SldBus(StrictModel):
    id: str
    name: str
    row: float
    col_start: float
    col_end: float
    voltage: str | None = None


class SldConnection(StrictModel):
    from_id: str
    to_id: str


class SiteSld(StrictModel):
    schema_version: int
    nodes: list[SldNode]
    buses: list[SldBus] = []
    connections: list[SldConnection] = []


class SiteSldResponse(StrictModel):
    site_id: int
    revision: int
    created_at: datetime
    updated_at: datetime
    sld: SiteSld
