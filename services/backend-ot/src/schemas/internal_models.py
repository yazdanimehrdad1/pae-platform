"""Internal Pydantic models for the polling pipeline (not exposed in the API)."""

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterMap(BaseModel):
    """Register address → raw value, returned from a Modbus read."""
    values: dict[int, int | bool] = Field(default_factory=dict)


class FailedScanRange(BaseModel):
    """A scan range that failed to read."""
    poll_kind: str
    start_index: int
    count: int
    status_code: int
    error_message: str


class DevicePollResult(BaseModel):
    """Merged result of polling all scan ranges for a device."""
    register_map: RegisterMap = Field(default_factory=RegisterMap)
    failed_ranges: list[FailedScanRange] = Field(default_factory=list)


class TimestampedValue(BaseModel):
    """One timestamped value of a point (a virtual point's input or its computed output)."""
    time: datetime
    value: float


class PointReading(BaseModel):
    """One reading of a point, with the point's metadata: a row of the readings queries
    (helpers.reads.device_points_readings). A computed virtual point reading has the same shape."""
    device_point_id: int
    register_address: int
    name: str
    data_type: str
    size: int
    unit: str | None = None
    scale_factor: float | None = None
    bitfield_detail: dict[str, str] | None = None
    enum_detail: dict[str, str] | None = None
    point_class: str | None = None
    severity: str | None = None
    # None only from the latest query: a point with no reading (or a virtual point without one).
    timestamp: datetime | None = None
    derived_value: float | None = None
