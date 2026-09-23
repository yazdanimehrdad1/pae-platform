"""
Modbus data mapping helpers.
"""

import struct
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from logger import get_logger
from schemas.db_models.orm_models import DevicePoint, DevicePointsReading
from schemas.internal_models import RegisterMap

logger = get_logger(__name__)


Quality = Literal[
    "GOOD",
    "BAD_ADDRESS",
    "BAD_REGISTER_COUNT",
    "BAD_CONVERSION",
    "BAD_DATA_TYPE",
    "BAD_EMPTY_DATA",
]
@dataclass
class RegisterExtractionResult:
    success: bool
    values: list[int]
    quality: Quality
    reason: str | None = None


@dataclass
class DecodeResult:
    success: bool
    value: float | int | bool | None
    quality: Quality
    reason: str | None = None


def _extract_register_values(
    register_map: dict[int, int | bool],
    point_address: int,
    size: int,
) -> RegisterExtractionResult:
    """
    Extract the raw register values for one point from a register map.

    Example:
        point_address = 1400, size = 2
        → reads register_map[1400] and register_map[1401]
    """
    if not register_map:
        return RegisterExtractionResult(
            success=False,
            values=[],
            quality="BAD_EMPTY_DATA",
            reason="Register map is empty",
        )

    if size < 1:
        return RegisterExtractionResult(
            success=False,
            values=[],
            quality="BAD_REGISTER_COUNT",
            reason=f"Invalid size={size}",
        )

    addresses = range(point_address, point_address + size)
    missing = [a for a in addresses if a not in register_map]
    if missing:
        return RegisterExtractionResult(
            success=False,
            values=[],
            quality="BAD_ADDRESS",
            reason=f"Register addresses {missing} not available in poll data",
        )

    return RegisterExtractionResult(
        success=True,
        values=[register_map[a] for a in addresses],
        quality="GOOD",
    )


def _apply_word_order(
    register_values: list[int],
    word_order: str = "msw_first",
) -> list[int]:
    """
    Controls register order.

    msw_first:
        [high_word, low_word]

    lsw_first:
        [low_word, high_word]
    """
    if word_order == "lsw_first":
        return list(reversed(register_values))
    return register_values


def _registers_to_bytes(
    register_values: list[int],
    byte_order: str = "big",
) -> bytes:
    """
    Converts 16-bit Modbus registers to bytes.

    Each Modbus register is 16 bits.
    big:
        0x1234 -> 12 34

    little:
        0x1234 -> 34 12
    """
    byte_data = bytearray()
    for reg in register_values:
        if byte_order == "little":
            byte_data.extend(reg.to_bytes(2, byteorder="little", signed=False))
        else:
            byte_data.extend(reg.to_bytes(2, byteorder="big", signed=False))
    return bytes(byte_data)


def _decode_modbus_point_value(
    register_values: list[int],
    data_type: str,
    byte_order: str = "big",
    word_order: str = "msw_first",
    scale: float = 1.0,
) -> DecodeResult:
    """
    Decode raw Modbus registers into final engineering value.

    This handles:
        uint16, int16
        uint32, int32
        float32
        uint64, int64
        float64
        bool
        raw/status_word
        bitfield, enum
    """
    try:
        ordered_registers = _apply_word_order(register_values, word_order)
        raw_bytes = _registers_to_bytes(ordered_registers, byte_order)

        data_type = data_type.lower()

        if data_type == "bool":
            value = bool(ordered_registers[0])

        elif data_type in ("uint16", "raw", "status_word16", "status_word32"):
            value = int.from_bytes(raw_bytes, byteorder="big", signed=False)

        elif data_type in ("bitfield16", "bitfield32", "enum16", "enum32"):
            value = int.from_bytes(raw_bytes, byteorder="big", signed=False)

        elif data_type == "int16":
            value = int.from_bytes(raw_bytes, byteorder="big", signed=True)

        elif data_type == "uint32":
            value = int.from_bytes(raw_bytes, byteorder="big", signed=False)

        elif data_type == "int32":
            value = int.from_bytes(raw_bytes, byteorder="big", signed=True)

        elif data_type == "float32":
            value = struct.unpack(">f", raw_bytes)[0]

        elif data_type == "uint64":
            value = int.from_bytes(raw_bytes, byteorder="big", signed=False)

        elif data_type == "int64":
            value = int.from_bytes(raw_bytes, byteorder="big", signed=True)

        elif data_type == "float64":
            value = struct.unpack(">d", raw_bytes)[0]

        else:
            return DecodeResult(
                success=False,
                value=None,
                quality="BAD_DATA_TYPE",
                reason=f"Unsupported data_type={data_type}",
            )

        if isinstance(value, (int, float)) and data_type != "bool":
            value = round(value * scale, 5)

        return DecodeResult(
            success=True,
            value=value,
            quality="GOOD",
        )

    except Exception as exc:
        return DecodeResult(
            success=False,
            value=None,
            quality="BAD_CONVERSION",
            reason=str(exc),
        )


def map_modbus_data_to_device_points(
    timestamp_dt: datetime,
    device_points_list: list[DevicePoint],
    register_map: RegisterMap,
    site_name: str = "",
    device_name: str = "",
) -> list[DevicePointsReading]:
    readings = []

    for point in device_points_list:
        extraction = _extract_register_values(
            register_map=register_map.values,
            point_address=point.address,
            size=point.size or 1,
        )

        if not extraction.success:
            logger.debug(
                "site_name='%s', device_name='%s', device_point_name='%s': "
                "register extraction failed (%s) — %s",
                site_name, device_name, point.name, extraction.quality, extraction.reason,
            )
            readings.append(
                DevicePointsReading(
                    timestamp=timestamp_dt,
                    device_point_id=point.id,
                    derived_value=None,
                )
            )
            continue

        decoded = _decode_modbus_point_value(
            register_values=extraction.values,
            data_type=point.data_type or "uint16",
            byte_order=point.byte_order or "big",
            word_order=point.word_order or "msw_first",
            scale=point.scale_factor or 1.0,
        )

        if not decoded.success:
            logger.debug(
                "site_name='%s', device_name='%s', device_point_name='%s': "
                "decode failed (%s) — %s",
                site_name, device_name, point.name, decoded.quality, decoded.reason,
            )

        readings.append(
            DevicePointsReading(
                timestamp=timestamp_dt,
                device_point_id=point.id,
                derived_value=decoded.value,
            )
        )

    return readings
