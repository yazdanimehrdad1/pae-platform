"""API response models."""

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field

from schemas.api_models.requests import Coordinates, DeviceScanRanges, Location


class HealthResponse(BaseModel):
    """Response model for health check."""
    ok: bool
    host: str
    port: int
    device_id: int = Field(..., description="Modbus unit/slave ID")
    detail: str | None = None


class DeviceListItem(BaseModel):
    """Response model for device data in list views."""
    device_id: int = Field(..., description="Device ID")
    site_id: int = Field(..., description="Site ID (4-digit number)")
    name: str = Field(..., description="Device name")
    type: str = Field(..., description="Device type")
    protocol: str = Field(..., description="Communication protocol")
    vendor: str | None = Field(None, description="Device vendor")
    model: str | None = Field(None, description="Device model")
    host: str = Field(..., description="Device hostname or IP address")
    port: int = Field(..., description="Device port")
    timeout: float | None = Field(default=None, description="Optional timeout (seconds)")
    server_address: int = Field(..., description="Server address")
    description: str | None = Field(None, description="Device description")
    poll_enabled: bool = Field(True, description="Whether polling is enabled for this device")
    read_from_aggregator: bool = Field(True, description="Whether to read from edge aggregator")
    scan_ranges: DeviceScanRanges | None = Field(None, description="Auto-computed or manually locked scan ranges")
    scan_ranges_locked: bool = Field(False, description="Whether scan ranges are locked against auto-recompute")
    modbus_address_mode: str = Field("zero_based", description="zero_based or one_based — controls pymodbus address offset")
    created_at: datetime = Field(..., description="Timestamp when device was created")
    updated_at: datetime = Field(..., description="Timestamp when device was last updated")
    deleted_at: datetime | None = Field(None, description="Soft-delete timestamp; null means active")

    model_config = {
        "from_attributes": True,
    }


class DeviceDeleteResponse(BaseModel):
    """Response model for a deleted device."""
    device_id: int = Field(..., description="Deleted device ID")
    site_id: int = Field(..., description="Site ID for the deleted device")
    mode: Literal["soft", "hard"] = Field(..., description="soft: device_id preserved and restorable; hard: permanently removed")



class DevicePointsCategoryGrouped(BaseModel):
    """Device points grouped by category."""
    standardized: list["DevicePointResponse"] = Field(default_factory=list)
    native: list["DevicePointResponse"] = Field(default_factory=list)
    virtual: list["DevicePointResponse"] = Field(default_factory=list)


# Backwards-compatible alias
DevicePoints = DevicePointsCategoryGrouped


class DeviceWithPoints(DeviceListItem):
    """Device response with its device points grouped by category."""
    points: DevicePointsCategoryGrouped = Field(default_factory=DevicePointsCategoryGrouped)


class SiteResponse(BaseModel):
    """Response model for site data."""
    site_id: int = Field(..., description="Site ID (4-digit number)")
    client_id: str = Field(..., description="Client identifier")
    name: str = Field(..., description="Site name")
    location: Location | None = Field(None, description="Site location details")
    operator: str = Field(..., description="Site operator")
    capacity: str = Field(..., description="Site capacity")
    device_count: int = Field(..., description="Number of devices at this site")
    description: str | None = Field(None, description="Site description")
    coordinates: Coordinates | None = Field(None, description="Geographic coordinates")
    created_at: datetime = Field(..., description="Timestamp when site was created")
    updated_at: datetime = Field(..., description="Timestamp when site was last updated")
    last_update: datetime = Field(..., description="Timestamp of last update")
    deleted_at: datetime | None = Field(None, description="Soft-delete timestamp; null means active")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


class SiteDeleteResponse(BaseModel):
    """Response model for a deleted site."""
    site_id: int = Field(..., description="Deleted site ID")
    mode: Literal["soft", "hard"] = Field(..., description="soft: site_id preserved and restorable; hard: permanently removed")


class SiteComprehensiveResponse(BaseModel):
    """Comprehensive site response with devices and their categorized points."""
    site_id: int = Field(..., description="Site ID (4-digit number)")
    client_id: str = Field(..., description="Client identifier")
    name: str = Field(..., description="Site name")
    location: Location | None = Field(None, description="Site location details")
    operator: str = Field(..., description="Site operator")
    capacity: str = Field(..., description="Site capacity")
    device_count: int = Field(..., description="Number of devices at this site")
    description: str | None = Field(None, description="Site description")
    coordinates: Coordinates | None = Field(None, description="Geographic coordinates")
    devices: list[DeviceWithPoints] = Field(default_factory=list, description="Devices with categorized points")
    created_at: datetime = Field(..., description="Timestamp when site was created")
    updated_at: datetime = Field(..., description="Timestamp when site was last updated")
    last_update: datetime = Field(..., description="Timestamp of last update")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }



class DevicePointResponse(BaseModel):
    """Response model for a device point."""
    id: int = Field(..., description="Primary key")
    site_id: int = Field(..., description="Site ID")
    device_id: int = Field(..., description="Device ID")
    name: str = Field(..., description="Point name")
    address: int = Field(..., description="Point address")
    size: int = Field(..., description="Point size")
    data_type: str = Field(..., description="Data type")
    scale_factor: float | None = Field(None, description="Scale factor")
    unit: str | None = Field(None, description="Unit")
    enum_detail: dict[str, str] | None = Field(None, description="Enum detail mapping")
    bitfield_detail: dict[str, str] | None = Field(None, description="Bitfield detail mapping")
    byte_order: str = Field("big-endian", description="Byte order for interpretation")
    word_order: str = Field("msw_first", description="Word order for multi-register types")
    poll_kind: str | None = Field(None, description="Register type: holding, input, or coils")
    category: str = Field("NATIVE", description="Point category: NATIVE, STANDARDIZED, or VIRTUAL")
    deleted_at: datetime | None = Field(None, description="Soft-delete timestamp; null means active")

    model_config = {
        "from_attributes": True,
    }


class TimeseriesPoint(BaseModel):
    time: datetime = Field(validation_alias=AliasChoices("time", "timestamp"))
    value: float | None = Field(None, validation_alias=AliasChoices("value", "derived_value"))
    translated_value: str | dict[str, int] | None = None

    model_config = {"populate_by_name": True}


class PointTimeseries(BaseModel):
    id: int = Field(validation_alias=AliasChoices("id", "device_point_id"))
    name: str
    data_type: str
    unit: str | None = None
    count: int = 0
    enum_map: dict[str, str] | None = None
    bit_labels: list[str] | None = None
    timeseries: list[TimeseriesPoint] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class PointLatest(BaseModel):
    id: int = Field(validation_alias=AliasChoices("id", "device_point_id"))
    name: str
    data_type: str
    unit: str | None = None
    time: datetime | None = Field(None, validation_alias=AliasChoices("time", "timestamp"))
    value: float | None = Field(None, validation_alias=AliasChoices("value", "derived_value"))
    translated_value: str | dict[str, int] | None = None

    model_config = {"populate_by_name": True}


class TimeseriesMeta(BaseModel):
    site_id: int
    device_id: int
    # Defaulted: the route serializes with response_model_exclude_none, so an unfiltered
    # request omits point_ids entirely.
    point_ids: list[int] | None = None
    total_count: int
    start_time: datetime | None = None
    end_time: datetime | None = None


class LatestMeta(BaseModel):
    site_id: int
    device_id: int
    point_ids: list[int] | None = None  # omitted when unfiltered (exclude_none)
    total_count: int


class TimeseriesResponse(BaseModel):
    meta: TimeseriesMeta
    readings: dict[str, PointTimeseries]


class LatestResponse(BaseModel):
    meta: LatestMeta
    readings: dict[str, PointLatest]


class DeviceHealthStatus(BaseModel):
    device_id: int
    name: str
    host: str
    port: int
    read_from_aggregator: bool
    poll_enabled: bool
    reachable: bool
    latency_ms: float | None = None
    error: str | None = None


class SiteDevicesHealthResponse(BaseModel):
    site_id: int
    total: int
    reachable: int
    unreachable: int
    devices: list[DeviceHealthStatus]


class CacheGetResponse(BaseModel):
    """Response model for retrieving a value from the cache."""
    key: str = Field(..., description="Cache key")
    value: Any = Field(..., description="Cached value, or None if the key is absent")
    exists: bool = Field(..., description="Whether the key exists in the cache")
