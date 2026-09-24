"""The dev seed is built from, and agrees with, the mock-modbus register-map contract.

Invariant guarded: every device and register mock-modbus publishes in
`contracts/modbus/mock-modbus.devices.json` becomes exactly one seeded device / NATIVE
point that addresses it correctly — same unit id, same 1-based address (one_based mode),
same register file, a data_type of the right width and signedness, and the same scale,
unit and labels. The committed contract is read as a static fixture (no DB/network).
"""

import pytest
from seed_db.mock_modbus_seed import (
    build_device,
    build_point,
    build_seed,
    default_contract_path,
    load_contract,
    point_data_type,
    seed_device_name,
)

from helpers.device_points.address_overlap import NativePointRange, validate_no_register_overlap
from schemas.api_models.types import register_size
from schemas.tests_models import MockModbusContract, MockModbusDevice, MockModbusRegister

SITE_NAME = "Alpha Solar Farm"


def _register(**overrides: object) -> MockModbusRegister:
    fields: dict[str, object] = {
        "file": "holding",
        "address": 101,
        "name": "active_power",
        "width": 16,
        "signed": False,
        "value_source": "random",
        "unit": "W",
        "scale": 0.1,
        "min": 0,
        "max": 1000,
        "enum_values": None,
        "bit_flags": None,
    }
    fields.update(overrides)
    return MockModbusRegister.model_validate(fields)


def _device(**overrides: object) -> MockModbusDevice:
    fields: dict[str, object] = {
        "unit_id": 2,
        "name": "device_2",
        "device_type": "bess",
        "kw_max": 10.0,
        "per_device_port": 5021,
        "registers": [],
    }
    fields.update(overrides)
    return MockModbusDevice.model_validate(fields)


@pytest.fixture(scope="module")
def contract() -> MockModbusContract:
    return load_contract(default_contract_path())


class TestDataTypeMapping:
    @pytest.mark.parametrize(
        ("overrides", "expected"),
        [
            ({}, "uint16"),
            ({"signed": True, "min": -500}, "int16"),
            ({"width": 32, "max": 500_000_000}, "uint32"),
            ({"width": 32, "signed": True, "min": -1}, "int32"),
            ({"enum_values": {"1": "off", "2": "on"}}, "enum16"),
            ({"width": 32, "enum_values": {"1": "off"}}, "enum32"),
            ({"bit_flags": {"0": "overvoltage"}}, "bitfield16"),
            ({"width": 32, "bit_flags": {"0": "overvoltage"}}, "bitfield32"),
        ],
    )
    def test_width_sign_and_labels_pick_the_type(
        self, overrides: dict[str, object], expected: str
    ) -> None:
        assert point_data_type(_register(**overrides)) == expected

    def test_flag_register_without_bit_labels_stays_numeric(self) -> None:
        # e.g. mock "alarm_flags": a bitmask with no per-bit labels to decode into.
        assert point_data_type(_register(name="alarm_flags", max=255)) == "uint16"


class TestBuildPoint:
    def test_carries_address_file_scale_unit_and_labels(self) -> None:
        register = _register(file="input", address=1104, enum_values={"1": "idle"})
        point = build_point(register)
        assert point.address == 1104
        assert point.poll_kind == "input"
        assert point.name == "active_power"
        assert point.scale_factor == 0.1
        assert point.unit == "W"
        assert point.enum_detail == {"1": "idle"}
        assert point.bitfield_detail is None
        assert point.category == "NATIVE"

    def test_size_matches_the_data_type(self) -> None:
        point = build_point(_register(width=32, max=500_000_000))
        assert point.size == register_size(point.data_type) == 2


class TestBuildDevice:
    def test_addresses_the_mock_unit_through_the_aggregator(self) -> None:
        seed_device = build_device(_device(), SITE_NAME)
        device = seed_device.device
        assert seed_device.site_name == SITE_NAME
        assert device.name == "mock-device-2"
        assert device.type == "BESS"
        assert device.server_address == 2
        assert device.read_from_aggregator is True
        # The contract numbers registers 1-based; backend-ot must subtract 1 on the wire.
        assert device.modbus_address_mode == "one_based"


class TestSeedAgreesWithCommittedContract:
    def test_contract_declares_one_based_numbering(self, contract: MockModbusContract) -> None:
        assert contract.register_numbering == "one_based"

    def test_one_seeded_device_per_mock_device(self, contract: MockModbusContract) -> None:
        devices, _points = build_seed(contract, SITE_NAME)
        assert sorted(seed.device.server_address for seed in devices) == sorted(
            device.unit_id for device in contract.devices
        )

    def test_every_register_becomes_exactly_one_point(self, contract: MockModbusContract) -> None:
        _devices, points = build_seed(contract, SITE_NAME)
        for device in contract.devices:
            seeded = {
                (point.poll_kind, point.address): point
                for point in points[seed_device_name(device)]
            }
            published = {(register.file, register.address) for register in device.registers}
            assert set(seeded) == published, device.name
            assert len(points[seed_device_name(device)]) == len(device.registers)

    def test_seeded_widths_match_published_widths(self, contract: MockModbusContract) -> None:
        _devices, points = build_seed(contract, SITE_NAME)
        for device in contract.devices:
            by_address = {
                (point.poll_kind, point.address): point
                for point in points[seed_device_name(device)]
            }
            for register in device.registers:
                point = by_address[(register.file, register.address)]
                assert point.size == register.width // 16, f"{device.name}.{register.name}"

    def test_no_seeded_points_overlap(self, contract: MockModbusContract) -> None:
        # Same rule the API enforces when points are created.
        _devices, points = build_seed(contract, SITE_NAME)
        for device_points in points.values():
            validate_no_register_overlap(
                [
                    NativePointRange(
                        name=point.name,
                        poll_kind=point.poll_kind or "holding",
                        address=point.address or 0,
                        size=point.size,
                    )
                    for point in device_points
                ]
            )
