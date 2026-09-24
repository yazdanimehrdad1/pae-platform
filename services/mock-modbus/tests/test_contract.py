"""The published register-map contract matches the device files.

Invariant guarded: ``contracts/modbus/mock-modbus.devices.json`` is exactly what
``make contract`` would write now. Change a device or register without regenerating it
and this fails, so consumers (backend-ot's dev seed) never build from a stale map.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.contract import render_contract
from app.modbus_mock_data import DEVICES

# services/mock-modbus/tests/ -> monorepo root (contracts/ is the only shared directory).
CONTRACT_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "modbus" / "mock-modbus.devices.json"
)


def test_committed_contract_is_current() -> None:
    assert CONTRACT_PATH.exists(), "missing contract: run `make -C services/mock-modbus contract`"
    committed = CONTRACT_PATH.read_bytes().decode("utf-8")
    assert committed == render_contract(DEVICES), (
        "contract is stale: run `make -C services/mock-modbus contract` and commit the result"
    )


def test_every_register_is_published() -> None:
    published = json.loads(render_contract(DEVICES))
    published_count = sum(len(device["registers"]) for device in published["devices"])
    declared_count = sum(
        len(device.holding_registers) + len(device.input_registers) for device in DEVICES
    )
    assert published_count == declared_count
