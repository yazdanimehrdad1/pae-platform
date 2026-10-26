"""API request models."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from helpers.common.date_time import resolve_timezone
from schemas.api_models.single_line_diagram import SiteSld
from schemas.api_models.types import DataType, DeviceType, PointClass, Severity, register_size
from schemas.api_models.virtual_points import VirtualPointDefinition


def _normalize_device_type(device_type: object) -> object:
    """Accept any casing for device type; canonical storage form is UPPERCASE."""
    return device_type.upper() if isinstance(device_type, str) else device_type


def _normalize_uppercase(value: object) -> object:
    """Accept any casing for an UPPERCASE enum value (e.g. point class, severity)."""
    return value.upper() if isinstance(value, str) else value


def _canonical_timezone(timezone_name: str | None) -> str | None:
    """Store a site time zone as its canonical IANA name ('pt' and 'PDT' become 'America/Los_Angeles')."""
    return resolve_timezone(timezone_name).key if timezone_name is not None else None


def _canonical_timezone_or_utc(timezone_name: str | None) -> str:
    """A new site's time zone: the canonical name, or UTC when omitted."""
    return _canonical_timezone(timezone_name) or "UTC"


SITE_TIMEZONE_DESCRIPTION = (
    "IANA time zone of the site (e.g. 'America/Los_Angeles'); local days and report schedules "
    "resolve in it. Case-insensitive, US shorthands such as 'PT' accepted; stored canonical"
)


class Coordinates(BaseModel):
    """Coordinates model for site location."""
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")
    elevation_m: float | None = Field(
        None, ge=-500, le=9000, description="Elevation above sea level, meters; omit if unknown"
    )


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
    profile: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Site profile key selecting the site's endpoints (e.g. 'alpha_solar'); a profile belongs to at most one site. Omit for a site without site-specific code",
    )
    # Optional on the wire (generated clients would otherwise require it); always set once validated.
    timezone: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        validate_default=True,
        description=f"{SITE_TIMEZONE_DESCRIPTION}. Omit for UTC",
    )

    _normalize_timezone = field_validator("timezone")(_canonical_timezone_or_utc)


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
    profile: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        description="Site profile key selecting the site's endpoints (e.g. 'alpha_solar'); a profile belongs to at most one site. Omit to keep the current one; null removes it",
    )
    timezone: str | None = Field(
        None, min_length=1, max_length=64, description=f"{SITE_TIMEZONE_DESCRIPTION}. Omit (or null) to keep the current one"
    )

    _normalize_timezone = field_validator("timezone")(_canonical_timezone)



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
    point_class: PointClass | None = Field(
        None,
        alias="class",
        description="Signal class: ANALOG (metered/continuous), BINARY (state/status/flags), ALARM (warning/fault/error/trip), CONTROL (setpoint/command/config)",
    )
    severity: Severity | None = Field(None, description="Severity: HIGH, MEDIUM or LOW")
    record_enabled: bool = Field(
        True,
        description="Whether the poller stores this point's readings. Only NATIVE points can be false. "
        "On a bulk upsert of an existing point, leaving it out keeps the current value",
    )

    # "class" on the wire (a Python keyword), point_class in code; accept either on input.
    model_config = ConfigDict(populate_by_name=True)

    _normalize_class_and_severity = field_validator("point_class", "severity", mode="before")(
        _normalize_uppercase
    )

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
    point_class: PointClass | None = Field(
        None,
        alias="class",
        description="Signal class: ANALOG (metered/continuous), BINARY (state/status/flags), ALARM (warning/fault/error/trip), CONTROL (setpoint/command/config)",
    )
    severity: Severity | None = Field(None, description="Severity: HIGH, MEDIUM or LOW")
    record_enabled: bool | None = Field(
        None,
        description="Whether the poller stores this point's readings. Only NATIVE points can be false; "
        "turning it off is refused (409) while a standardized link, virtual point or user alarm reads the point",
    )

    # "class" on the wire (a Python keyword), point_class in code; accept either on input.
    model_config = ConfigDict(populate_by_name=True)

    _normalize_class_and_severity = field_validator("point_class", "severity", mode="before")(
        _normalize_uppercase
    )

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


class VirtualPointCreateRequest(BaseModel):
    """Create a VIRTUAL point. The server derives data_type/size from the definition's kind
    (condition → enum16 with enum_detail from the case labels, calculation → float32)."""
    name: str = Field(..., min_length=1, max_length=255)
    unit: str | None = Field(None, max_length=50)
    point_class: PointClass | None = Field(
        None,
        alias="class",
        description="Signal class: ANALOG (metered/continuous), BINARY (state/status/flags), ALARM (warning/fault/error/trip), CONTROL (setpoint/command/config)",
    )
    severity: Severity | None = Field(None, description="Severity: HIGH, MEDIUM or LOW")
    definition: VirtualPointDefinition = Field(
        ..., description="How the value is computed from other points on the site (computed on read, not stored)"
    )

    model_config = ConfigDict(populate_by_name=True)

    _normalize_class_and_severity = field_validator("point_class", "severity", mode="before")(
        _normalize_uppercase
    )


class VirtualPointUpdateRequest(BaseModel):
    """Update a VIRTUAL point; omitted fields keep their value. A new definition may change the kind."""
    name: str | None = Field(None, min_length=1, max_length=255)
    unit: str | None = Field(None, max_length=50)
    point_class: PointClass | None = Field(
        None,
        alias="class",
        description="Signal class: ANALOG (metered/continuous), BINARY (state/status/flags), ALARM (warning/fault/error/trip), CONTROL (setpoint/command/config)",
    )
    severity: Severity | None = Field(None, description="Severity: HIGH, MEDIUM or LOW")
    definition: VirtualPointDefinition | None = None

    model_config = ConfigDict(populate_by_name=True)

    _normalize_class_and_severity = field_validator("point_class", "severity", mode="before")(
        _normalize_uppercase
    )


class StandardizedPointLinkRequest(BaseModel):
    """Link a STANDARDIZED point to the NATIVE point on its device whose readings it shows."""
    source_point_id: int = Field(..., description="An active NATIVE point on the same device")
    unit: str | None = Field(None, max_length=50, description="Unit of the standardized point's values, e.g. 'kW'")
    scale_factor: float = Field(
        1.0,
        description="Source value x scale_factor = the standardized value; between power units it must convert them (W -> kW: 0.001)",
    )


class CacheSetRequest(BaseModel):
    """Request model for setting a value in the cache."""
    key: str = Field(..., description="Cache key")
    value: Any = Field(..., description="Value to cache")
    ttl: int | None = Field(None, description="Time-to-live in seconds; None means no expiry")


class SiteSldUpsertRequest(BaseModel):
    """Create or replace a site's single line diagram."""

    model_config = ConfigDict(extra="forbid")

    sld: SiteSld = Field(..., description="The whole diagram; it replaces the stored one")
    revision: int | None = Field(
        None,
        ge=1,
        description="The revision being replaced, as last read (409 if it is no longer current). Omit to create the site's first diagram",
    )


class PvArrayConfigUpsertRequest(BaseModel):
    """The PV array behind a PV or INVERTER device: orientation, ratings and losses."""

    model_config = ConfigDict(extra="forbid")

    tilt_deg: float = Field(..., ge=0, le=90, description="Module tilt from horizontal, degrees (0 = flat)")
    azimuth_deg: float = Field(
        ..., ge=0, lt=360, description="Direction the modules face, degrees clockwise from north (180 = south)"
    )
    dc_capacity_kw: float = Field(..., gt=0, description="DC nameplate of the array, kW (kWp)")
    ac_capacity_kw: float = Field(..., gt=0, description="AC limit of the inverter(s) feeding this array, kW")
    system_loss_pct: float = Field(
        14.0, ge=0, lt=100, description="Lumped system losses (soiling, wiring, mismatch, inverter), percent"
    )
    temp_coefficient_pct_per_c: float = Field(
        -0.35, ge=-2, le=0, description="Module power temperature coefficient, percent per degC (negative)"
    )
