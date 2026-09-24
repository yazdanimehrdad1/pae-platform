"""Build the dev seed's devices and points from the mock-modbus register-map contract.

mock-modbus publishes every device and register it serves to
`contracts/modbus/mock-modbus.devices.json` (generated there by `make contract`). Seeding
from that file, instead of hand-writing points, means the dev historian polls exactly
what the simulator serves: same unit ids, same addresses, same widths, and nothing to
keep in sync by hand. The two services share only that file, never code.

Mapping (one device per contract device, one NATIVE point per register):

    unit_id                  -> server_address (aggregator selects the device by it)
    register address         -> point address, with modbus_address_mode="one_based"
                                (the contract's numbering; backend-ot sends address-1)
    file (holding / input)   -> poll_kind
    width / signed / enum /  -> data_type: enum16|32, bitfield16|32 (only when bit labels
    bit_flags                   exist), int16|32 when signed, else uint16|32
    scale, unit, name        -> scale_factor, unit, name
    enum_values / bit_flags  -> enum_detail / bitfield_detail
"""

from __future__ import annotations

from pathlib import Path

from schemas.api_models.requests import DeviceCreateRequest, DevicePointCreateRequest
from schemas.api_models.types import DataType, DeviceType, register_size
from schemas.tests_models import (
    MockModbusContract,
    MockModbusDevice,
    MockModbusRegister,
    SeedDevice,
)

CONTRACT_FILENAME = "mock-modbus.devices.json"

# Service name of mock-modbus on the compose network. Only used for direct (non-aggregator)
# reads; seeded devices read through the aggregator (AGGREGATOR_MODBUS_HOST/PORT).
MOCK_MODBUS_HOST = "mock-modbus"

_DEVICE_TYPES: dict[str, DeviceType] = {"pv": "PV", "bess": "BESS", "ied": "IED"}


def default_contract_path() -> Path:
    """Where the seeder finds the contract.

    Inside the app container `make seed-db` copies it next to this file; on the host it
    is read from the monorepo's `contracts/` (services/backend-ot/tests/seed_db -> root).
    """
    here = Path(__file__).resolve()
    sibling = here.parent / CONTRACT_FILENAME
    if sibling.exists():
        return sibling
    if len(here.parents) > 4:
        repo_contract = here.parents[4] / "contracts" / "modbus" / CONTRACT_FILENAME
        if repo_contract.exists():
            return repo_contract
    raise FileNotFoundError(
        f"{CONTRACT_FILENAME} not found next to {here.name} or in the monorepo contracts/ "
        "directory; generate it with `make -C services/mock-modbus contract`"
    )


def load_contract(path: Path) -> MockModbusContract:
    return MockModbusContract.model_validate_json(path.read_bytes())


def point_data_type(register: MockModbusRegister) -> DataType:
    wide = register.width == 32
    if register.enum_values:
        return "enum32" if wide else "enum16"
    if register.bit_flags:
        return "bitfield32" if wide else "bitfield16"
    if register.signed:
        return "int32" if wide else "int16"
    return "uint32" if wide else "uint16"


def seed_device_name(device: MockModbusDevice) -> str:
    return f"mock-{device.name.replace('_', '-')}"


def build_device(device: MockModbusDevice, site_name: str) -> SeedDevice:
    return SeedDevice(
        site_name=site_name,
        device=DeviceCreateRequest(
            name=seed_device_name(device),
            type=_DEVICE_TYPES[device.device_type],
            protocol="Modbus",
            vendor="PAE mock-modbus",
            model=device.name,
            host=MOCK_MODBUS_HOST,
            port=device.per_device_port,
            timeout=5.0,
            server_address=device.unit_id,
            description=(
                f"Simulated {device.device_type} on mock-modbus unit {device.unit_id}; "
                f"seeded from contracts/modbus/{CONTRACT_FILENAME}"
            ),
            poll_enabled=True,
            read_from_aggregator=True,
            modbus_address_mode="one_based",
        ),
    )


def build_point(register: MockModbusRegister) -> DevicePointCreateRequest:
    data_type = point_data_type(register)
    return DevicePointCreateRequest(
        address=register.address,
        name=register.name,
        poll_kind=register.file,
        data_type=data_type,
        size=register_size(data_type),
        scale_factor=register.scale,
        unit=register.unit,
        enum_detail=register.enum_values,
        bitfield_detail=register.bit_flags,
    )


def build_seed(
    contract: MockModbusContract, site_name: str
) -> tuple[list[SeedDevice], dict[str, list[DevicePointCreateRequest]]]:
    """Seed devices, and their points keyed by seeded device name."""
    devices = [build_device(device, site_name) for device in contract.devices]
    points = {
        seed_device_name(device): [build_point(register) for register in device.registers]
        for device in contract.devices
    }
    return devices, points
