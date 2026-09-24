"""End-to-end: a real server process, read over raw Modbus TCP like a device client.

Invariant guarded: every register declared in every device file is reachable through
the aggregator by its device's unit_id, at the standard 1-based address, and serves a
value its spec allows. Unmapped addresses serve the default, and writes change nothing.
Expectations are derived from the device files themselves, so adding a device or a
register extends these tests automatically.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from conftest import RunningServer
from modbus_frames import (
    READ_HOLDING_REGISTERS,
    READ_INPUT_REGISTERS,
    ModbusTcpClient,
    to_signed_16,
    to_signed_32,
    wire_address_for,
)

from app.modbus_mock_data import DEVICES
from app.models import DeviceSpec, RegisterSpec
from app.server import _static_profile_for

REGISTER_FILES = (
    ("holding", READ_HOLDING_REGISTERS),
    ("input", READ_INPUT_REGISTERS),
)


def _all_registers() -> list[pytest.param]:
    params = []
    for device in DEVICES:
        for file_name, function_code in REGISTER_FILES:
            register_map: dict[int, RegisterSpec] = getattr(device, f"{file_name}_registers")
            for key, spec in sorted(register_map.items()):
                params.append(
                    pytest.param(
                        device, function_code, key, spec, id=f"{device.name}-{file_name}-{key}"
                    )
                )
    return params


def _allowed_static_values(device: DeviceSpec, key: int) -> set[int]:
    """Every value the frozen table holds for this address, as served on the wire."""
    table = _static_profile_for(device)
    assert table is not None, f"{device.name} declares profile_static registers but has no table"
    return {row[key] & 0xFFFF for row in table.rows.values()}


@pytest.fixture(scope="module")
def client(server: RunningServer) -> Iterator[ModbusTcpClient]:
    with ModbusTcpClient(server.host, server.port) as modbus_client:
        yield modbus_client


class TestEveryDeclaredRegister:
    @pytest.mark.parametrize(("device", "function_code", "key", "spec"), _all_registers())
    def test_serves_a_value_its_spec_allows(
        self,
        client: ModbusTcpClient,
        server: RunningServer,
        device: DeviceSpec,
        function_code: int,
        key: int,
        spec: RegisterSpec,
    ) -> None:
        wire_address = wire_address_for(key, server.zero_mode)

        if spec.width == 32:
            high, low = client.read_registers(function_code, wire_address, 2, device.unit_id)
            raw = (high << 16) | low
            value = to_signed_32(raw) if spec.min < 0 else raw
            assert spec.min <= value <= spec.max
            return

        (raw,) = client.read_registers(function_code, wire_address, 1, device.unit_id)
        if spec.type == "profile_static":
            assert raw in _allowed_static_values(device, key)
        else:
            value = to_signed_16(raw) if spec.min < 0 else raw
            assert spec.min <= value <= spec.max


class TestUnmappedAndWrites:
    # Far above every device's band, in both register files.
    UNMAPPED_KEY = 60_000

    @pytest.mark.parametrize("device", DEVICES, ids=lambda device: device.name)
    @pytest.mark.parametrize(("file_name", "function_code"), REGISTER_FILES)
    def test_unmapped_address_serves_the_default(
        self,
        client: ModbusTcpClient,
        server: RunningServer,
        device: DeviceSpec,
        file_name: str,
        function_code: int,
    ) -> None:
        wire_address = wire_address_for(self.UNMAPPED_KEY, server.zero_mode)
        values = client.read_registers(function_code, wire_address, 3, device.unit_id)
        assert values == [server.default_register_value] * 3

    def test_writes_are_accepted_and_discarded(
        self, client: ModbusTcpClient, server: RunningServer
    ) -> None:
        device = DEVICES[0]
        wire_address = wire_address_for(self.UNMAPPED_KEY, server.zero_mode)
        client.write_register(wire_address, 4321, device.unit_id)
        (value,) = client.read_registers(READ_HOLDING_REGISTERS, wire_address, 1, device.unit_id)
        assert value == server.default_register_value
