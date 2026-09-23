"""Shared register decode logic for live stream and poll history."""

from typing import Protocol

from helpers.modbus.modbus_data_mapping import _decode_modbus_point_value
from schemas.api_models import NumericDataType, register_size
from schemas.api_models.live_stream_raw_registers import (
    LiveStreamRawRegistersRegister,
    LiveStreamRawRegistersRegisterConfig,
)


class RegisterDecodeParams(Protocol):
    start_address: int
    end_address: int
    byte_order: str
    word_order: str

    def int_register_configs(self) -> dict[int, LiveStreamRawRegistersRegisterConfig]: ...


def build_registers(
    registers_raw: list[int],
    params: RegisterDecodeParams,
) -> dict[str, LiveStreamRawRegistersRegister]:
    configs = params.int_register_configs()
    count = params.end_address - params.start_address + 1

    consumed: set[int] = set()
    for addr, configured in configs.items():
        for j in range(1, register_size(configured.data_type)):
            consumed.add(addr + j)

    registers: dict[str, LiveStreamRawRegistersRegister] = {}
    i = 0
    while i < count:
        addr = params.start_address + i
        cfg = configs.get(addr)

        if addr in consumed:
            i += 1
            continue

        data_type: NumericDataType = cfg.data_type if cfg else "int16"
        size = register_size(data_type)
        raw_vals = registers_raw[i:i + size]

        effective_byte_order = (cfg.byte_order if cfg and cfg.byte_order else None) or params.byte_order
        effective_word_order = (cfg.word_order if cfg and cfg.word_order else None) or params.word_order
        result = _decode_modbus_point_value(
            register_values=raw_vals,
            data_type=data_type,
            byte_order=effective_byte_order,
            word_order=effective_word_order,
        )
        value = result.value if result.success else None

        registers[str(addr)] = LiveStreamRawRegistersRegister(
            value=value,
            label=(cfg.label if cfg else None) or "unknown",
            data_type=data_type,
        )
        i += size

    return registers
