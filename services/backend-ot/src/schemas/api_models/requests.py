"""API request models."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from schemas.api_models.types import DataType, DeviceType, register_size


def _normalize_device_type(device_type: object) -> object:
    """Accept any casing for device type; canonical storage form is UPPERCASE."""
    return device_type.upper() if isinstance(device_type, str) else device_type


class Coordinates(BaseModel):
    """Coordinates model for site location."""
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")


class Location(BaseModel):
    """Location model for site address details."""
    street: str = Field(..., min_length=1, max_length=255, description="Street address")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State/province")
    zip_code: int = Field(..., ge=0, description="Zip/postal code")



class DeviceCreateRequest(BaseModel):
    """Request model for creating a new device."""
    name: str = Field(..., min_length=1, max_length=255, description="Unique device name/identifier")
    type: DeviceType = Field(
        ..., description="Device type. Case-insensitive on input; stored uppercase."
    )
    protocol: Literal["Modbus", "DNP"] = Field(
        default="Modbus", description="Communication protocol"
    )
    vendor: str | None = Field(default=None, max_length=255, description="Device vendor")
    model: str | None = Field(default=None, max_length=255, description="Device model")
    host: str = Field(..., min_length=1, max_length=255, description="Device hostname or IP address")
    port: int = Field(default=502, ge=1, le=65535, description="Device port (default: 502)")
    timeout: float | None = Field(default=None, ge=0, description="Optional timeout (seconds)")
    server_address: int = Field(default=1, ge=1, description="Server address (default: 1)")
    description: str | None = Field(default=None, description="Optional device description")
    poll_enabled: bool = Field(True, description="Whether polling is enabled for this device")
    read_from_aggregator: bool = Field(True, description="Whether to read from edge aggregator")
    modbus_address_mode: Literal["zero_based", "one_based"] = Field(
        "zero_based",
        description="zero_based: use addresses as-is; one_based: subtract 1 before sending to pymodbus (for devices whose docs use 1-based numbering)"
    )
    scan_ranges: Optional["DeviceScanRanges"] = Field(None, description="Initial scan ranges (optional)")

    _normalize_type = field_validator("type", mode="before")(_normalize_device_type)


class DeviceUpdate(BaseModel):
    """Request model for updating a device."""
    name: str | None = Field(None, min_length=1, max_length=255, description="Device name/identifier")
    type: DeviceType | None = Field(
        None, description="Device type. Case-insensitive on input; stored uppercase."
    )
    protocol: Literal["Modbus", "DNP"] | None = Field(
        None, description="Communication protocol"
    )
    vendor: str | None = Field(None, max_length=255, description="Device vendor")
    model: str | None = Field(None, description="Device model")
    host: str | None = Field(
        None, min_length=1, max_length=255, description="Device hostname or IP address"
    )
    port: int | None = Field(None, ge=1, le=65535, description="Device port")
    timeout: float | None = Field(default=None, ge=0, description="Optional timeout (seconds)")
    server_address: int | None = Field(None, ge=1, description="Server address")
    description: str | None = Field(None, description="Device description")
    poll_enabled: bool | None = Field(None, description="Whether polling is enabled for this device")
    read_from_aggregator: bool | None = Field(
        None, description="Whether to read from edge aggregator"
    )
    modbus_address_mode: Literal["zero_based", "one_based"] | None = Field(
        None,
        description="zero_based: use addresses as-is; one_based: subtract 1 before sending to pymodbus"
    )
    scan_ranges: Optional["DeviceScanRanges"] = Field(None, description="Updated scan ranges (does not lock)")

    _normalize_type = field_validator("type", mode="before")(_normalize_device_type)


class SiteCreateRequest(BaseModel):
    """Request model for creating a new site."""
    client_id: str = Field(..., min_length=1, max_length=255, description="Client identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Site name")
    location: Location = Field(..., description="Site location details")
    operator: str = Field(..., min_length=1, max_length=255, description="Site operator")
    capacity: str = Field(..., min_length=1, max_length=255, description="Site capacity")
    description: str | None = Field(default=None, description="Optional site description")
    coordinates: Coordinates | None = Field(
        default=None, description="Geographic coordinates"
    )


class SiteUpdateRequest(BaseModel):
    """Request model for updating a site."""
    client_id: str | None = Field(
        None, min_length=1, max_length=255, description="Client identifier"
    )
    name: str | None = Field(None, min_length=1, max_length=255, description="Site name")
    location: Location | None = Field(None, description="Site location details")
    operator: str | None = Field(None, description="Site operator")
    capacity: str | None = Field(None, min_length=1, max_length=255, description="Site capacity")
    description: str | None = Field(None, description="Site description")
    coordinates: Coordinates | None = Field(None, description="Geographic coordinates")



class PollingConfig(BaseModel):
    """Polling configuration for Modbus reads."""
    poll_address: int = Field(..., ge=0, le=65535, description="Start register address")
    poll_count: int = Field(..., ge=1, description="Number of registers to read")
    poll_kind: Literal["holding", "input", "coils", "discretes"] = Field(
        ..., description="Register type to read"
    )


class RegisterRange(BaseModel):
    """A single Modbus read window."""
    start_index: int = Field(..., ge=0, le=65535)
    count: int = Field(..., ge=1)


class DeviceScanRanges(BaseModel):
    """Scan ranges categorized by register type."""
    holding: list[RegisterRange] = Field(default_factory=list)
    input: list[RegisterRange] = Field(default_factory=list)
    coils: list[RegisterRange] = Field(default_factory=list)


class DevicePointCreateRequest(BaseModel):
    """Request model for creating a device point directly (Config-free)."""
    name: str = Field(..., min_length=1, max_length=255)
    poll_kind: Literal["holding", "input", "coils"] | None = None
    address: int | None = Field(None, ge=0, le=65535)
    size: int = Field(..., ge=1)
    data_type: DataType = Field(
        ...,
        description="Register interpretation. Width is encoded in the type (e.g. enum32, bitfield16); `size` must match register_size(data_type).",
    )
    scale_factor: float | None = None
    unit: str | None = None
    byte_order: str = "big-endian"
    word_order: str = "msw_first"
    bitfield_detail: dict[str, str] | None = None
    enum_detail: dict[str, str] | None = None
    category: Literal["NATIVE", "STANDARDIZED", "VIRTUAL"] = "NATIVE"

    @model_validator(mode="after")
    def _check_size_matches_type(self) -> "DevicePointCreateRequest":
        expected = register_size(self.data_type)
        if self.size != expected:
            raise ValueError(
                f"data_type '{self.data_type}' requires size={expected}, got size={self.size}"
            )
        return self


class DevicePointUpdateRequest(BaseModel):
    """Request model for updating a device point."""
    name: str | None = Field(None, min_length=1, max_length=255)
    poll_kind: Literal["holding", "input", "coils"] | None = None
    address: int | None = Field(None, ge=0, le=65535)
    size: int | None = Field(None, ge=1)
    data_type: DataType | None = Field(
        None,
        description="Register interpretation. Width is encoded in the type (e.g. enum32, bitfield16); `size` must match register_size(data_type).",
    )
    scale_factor: float | None = None
    unit: str | None = None
    byte_order: str | None = None
    word_order: str | None = None
    bitfield_detail: dict[str, str] | None = None
    enum_detail: dict[str, str] | None = None

    @model_validator(mode="after")
    def _check_size_matches_type(self) -> "DevicePointUpdateRequest":
        # Partial updates can only be validated here when both are supplied; the mixed
        # case (one field set) is enforced against effective values in the CRUD layer.
        if self.data_type is not None and self.size is not None:
            expected = register_size(self.data_type)
            if self.size != expected:
                raise ValueError(
                    f"data_type '{self.data_type}' requires size={expected}, got size={self.size}"
                )
        return self


class DevicePointsBulkRequest(BaseModel):
    """Bulk upsert: create new points and update existing ones (matched by name) in one call."""
    points: list[DevicePointCreateRequest] = Field(..., min_length=1)


class CacheSetRequest(BaseModel):
    """Request model for setting a value in the cache."""
    key: str = Field(..., description="Cache key")
    value: Any = Field(..., description="Value to cache")
    ttl: int | None = Field(None, description="Time-to-live in seconds; None means no expiry")
