"""Typed helpers for API models."""

from typing import Literal, TypeAlias, get_args

from pydantic import BaseModel
from typing_extensions import TypedDict

# Supported Modbus data types. These must stay in sync with the decode branches in
# helpers/modbus/modbus_data_mapping._decode_modbus_point_value — anything else decodes
# to BAD_DATA_TYPE and silently stores a null reading.
#
# Layered on purpose:
#   NumericDataType  — decodes to a number from the registers alone. Safe anywhere,
#                      including the live-stream path, which reads ad-hoc registers with
#                      no enum_detail/bitfield_detail to interpret them against.
#   ExtendedDataType — only meaningful for stored device points, where the point carries
#                      the detail map used to translate the value.
#
# Every type is self-describing: its width is derivable from the name (see
# _REGISTER_WIDTHS / register_size). The semantic types carry an explicit 16/32 suffix
# for the same reason int32/float64 do — so a 32-bit enum/bitfield/status_word can be read
# without depending on a separate `size` field.
NumericDataType = Literal[
    "bool",
    "uint16",
    "int16",
    "uint32",
    "int32",
    "uint64",
    "int64",
    "float32",
    "float64",
    "raw",
]

ExtendedDataType = Literal[
    "enum16",
    "enum32",
    "bitfield16",
    "bitfield32",
    "status_word16",
    "status_word32",
]

# PEP 586 flattens nested Literals, so get_args() below yields plain strings.
DataType = Literal[NumericDataType, ExtendedDataType]

SUPPORTED_NUMERIC_DATA_TYPES: frozenset[str] = frozenset(get_args(NumericDataType))
SUPPORTED_DATA_TYPES: frozenset[str] = frozenset(get_args(DataType))


# Register count each data type occupies (1 register = 16 bits). Single source of truth
# for width across the poll path, the live-stream path, and size validation. Keys must
# stay identical to SUPPORTED_DATA_TYPES (guarded by a unit test).
_REGISTER_WIDTHS: dict[str, int] = {
    "bool": 1,
    "uint16": 1,
    "int16": 1,
    "raw": 1,
    "enum16": 1,
    "bitfield16": 1,
    "status_word16": 1,
    "uint32": 2,
    "int32": 2,
    "float32": 2,
    "enum32": 2,
    "bitfield32": 2,
    "status_word32": 2,
    "uint64": 4,
    "int64": 4,
    "float64": 4,
}


def register_size(data_type: DataType) -> int:
    """Number of 16-bit registers a data type occupies."""
    return _REGISTER_WIDTHS[data_type]


# Device types. Union of what the API historically accepted and the keys of
# helpers/device_points/device_standardized_points._STANDARDIZED_POINTS. Canonical form
# is UPPERCASE; request models normalize incoming casing before validation.
# METER and RTAC are valid but have no standardized-point templates yet.
DeviceType = Literal[
    "BESS",
    "ES",
    "INVERTER",
    "PV",
    "GENERATOR",
    "LOADBANK",
    "RELAY",
    "IED",
    "METER",
    "RTAC",
]

SUPPORTED_DEVICE_TYPES: frozenset[str] = frozenset(get_args(DeviceType))

# What kind of signal a device point carries (API/DB name "class"):
#   ANALOG  - metered and continuous values (power, voltage, SOC, energy, temperature)
#   BINARY  - state and status: on/off, mode, health and diagnostic flags
#   ALARM   - anything abnormal: warning, alarm, fault, error, trip
#   CONTROL - setpoints, commands, configuration
PointClass = Literal["ANALOG", "BINARY", "ALARM", "CONTROL"]

SUPPORTED_POINT_CLASSES: frozenset[str] = frozenset(get_args(PointClass))

Severity = Literal["HIGH", "MEDIUM", "LOW"]

SUPPORTED_SEVERITIES: frozenset[str] = frozenset(get_args(Severity))


class DevicePointData(BaseModel):
    """Pydantic model for a device point row to be written to the database."""
    site_id: int
    device_id: int
    address: int
    name: str
    size: int
    data_type: DataType
    category: Literal["NATIVE", "STANDARDIZED", "VIRTUAL"] = "NATIVE"
    point_class: PointClass | None = None
    severity: Severity | None = None
    scale_factor: float | None = None
    unit: str | None = None
    bitfield_detail: dict[str, str] | None = None
    enum_detail: dict[str, str] | None = None
    byte_order: str = "big-endian"
    word_order: str = "msw_first"


class PollResult(TypedDict, total=False):
    """Result of polling a single device."""
    device_name: str
    success: bool
    cache_successful: int
    cache_failed: int
    db_successful: int
    db_failed: int
    error: str | None


ModbusRegisterValues: TypeAlias = list[int | bool]


BitfieldDetailMap: TypeAlias = dict[str, str]
EnumDetailMap: TypeAlias = dict[str, str]
