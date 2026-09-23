"""Internal Pydantic models for the polling pipeline (not exposed in the API)."""

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
