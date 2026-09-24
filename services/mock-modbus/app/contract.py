"""The published register-map contract: what every mock device serves, as plain JSON.

Other services must not import this package (monorepo rule: services share only
``contracts/``), so the device files are exported to
``contracts/modbus/mock-modbus.devices.json`` by ``scripts/export_contract.py``
(``make contract``). Consumers — today backend-ot's dev seed — build from that file, so
they cannot disagree with what this server actually serves.

The output is deterministic (sorted, fixed key order) so it diffs cleanly and a drift
test can compare it byte for byte.
"""
from __future__ import annotations

import json
from typing import Any

from app.models import DeviceSpec, RegisterSpec

CONTRACT_NAME = "mock-modbus/devices"
CONTRACT_VERSION = 1


def _register_entry(file_name: str, address: int, spec: RegisterSpec) -> dict[str, Any]:
    return {
        "file": file_name,
        "address": address,
        "name": spec.name,
        "width": spec.width,
        "signed": spec.min < 0,
        "value_source": spec.type,
        "unit": spec.unit,
        "scale": spec.scale,
        "min": spec.min,
        "max": spec.max,
        "enum_values": (
            {str(value): label for value, label in sorted(spec.enum_values.items())}
            if spec.enum_values
            else None
        ),
        "bit_flags": (
            {str(bit): label for bit, label in sorted(spec.bit_flags.items())}
            if spec.bit_flags
            else None
        ),
    }


def _device_entry(device: DeviceSpec) -> dict[str, Any]:
    registers = [
        _register_entry(file_name, address, spec)
        for file_name, register_map in (
            ("holding", device.holding_registers),
            ("input", device.input_registers),
        )
        for address, spec in sorted(register_map.items())
    ]
    return {
        "unit_id": device.unit_id,
        "name": device.name,
        "device_type": device.device_type.value,
        "kw_max": device.kw_max,
        "per_device_port": device.port,
        "registers": registers,
    }


def build_contract(devices: list[DeviceSpec]) -> dict[str, Any]:
    return {
        "$comment": (
            "GENERATED from services/mock-modbus/app/modbus_mock_data by "
            "`make -C services/mock-modbus contract`. Do not edit by hand."
        ),
        "contract": CONTRACT_NAME,
        "version": CONTRACT_VERSION,
        # Addresses are 1-based register numbers, as a standard Modbus client types them.
        # The server runs ZERO_MODE=false, so a client sends wire address = address - 1
        # (backend-ot: modbus_address_mode="one_based").
        "register_numbering": "one_based",
        # All devices are served on one aggregator port, selected by unit_id; per-device
        # ports are only used when PER_DEVICE_ENABLED=true.
        "devices": [_device_entry(device) for device in sorted(devices, key=lambda d: d.unit_id)],
    }


def render_contract(devices: list[DeviceSpec]) -> str:
    return json.dumps(build_contract(devices), indent=2, ensure_ascii=False) + "\n"
