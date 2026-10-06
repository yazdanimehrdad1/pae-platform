"""
The published contracts match the code.

Invariant guarded: ``contracts/openapi/powerflow.openapi.json``,
``contracts/powerflow/points.json``, ``contracts/modbus/powerflow.registers.json`` and
``contracts/powerflow/sites.json`` are exactly what ``make contract`` would write now, so
consumers never build against a stale API, point list, Modbus register layout or site topology.
"""

import json
from pathlib import Path

from conftest import DEFAULT_SITES, POINT_STANDARD, default_site

from powerflow.app import create_app
from powerflow.contract import (
    render_openapi_contract,
    render_points_contract,
    render_registers_contract,
    render_sites_contract,
)
from powerflow.point_standard import build_layout

# services/powerflow/tests/ -> monorepo root (contracts/ is the only shared directory).
CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
OPENAPI_PATH = CONTRACTS_DIR / "openapi" / "powerflow.openapi.json"
POINTS_PATH = CONTRACTS_DIR / "powerflow" / "points.json"
REGISTERS_PATH = CONTRACTS_DIR / "modbus" / "powerflow.registers.json"
SITES_PATH = CONTRACTS_DIR / "powerflow" / "sites.json"
REGENERATE = "run `make -C services/powerflow contract` and commit the result"


class TestContracts:
    def test_committed_openapi_is_current(self) -> None:
        assert OPENAPI_PATH.exists(), f"missing contract: {REGENERATE}"
        committed = OPENAPI_PATH.read_bytes().decode("utf-8")
        assert committed == render_openapi_contract(create_app()), f"stale contract: {REGENERATE}"

    def test_committed_points_are_current(self) -> None:
        assert POINTS_PATH.exists(), f"missing points contract: {REGENERATE}"
        committed = POINTS_PATH.read_bytes().decode("utf-8")
        assert committed == render_points_contract(), f"stale points contract: {REGENERATE}"

    def test_committed_registers_are_current(self) -> None:
        assert REGISTERS_PATH.exists(), f"missing registers contract: {REGENERATE}"
        committed = REGISTERS_PATH.read_bytes().decode("utf-8")
        sites = DEFAULT_SITES
        expected = render_registers_contract(POINT_STANDARD, sites)
        assert committed == expected, f"stale registers contract: {REGENERATE}"

    def test_committed_sites_are_current(self) -> None:
        assert SITES_PATH.exists(), f"missing sites contract: {REGENERATE}"
        committed = SITES_PATH.read_bytes().decode("utf-8")
        expected = render_sites_contract(POINT_STANDARD, DEFAULT_SITES)
        assert committed == expected, f"stale sites contract: {REGENERATE}"

    def test_sites_and_registers_contracts_agree_on_devices(self) -> None:
        sites = json.loads(SITES_PATH.read_text(encoding="utf-8"))["sites"]
        registers = json.loads(REGISTERS_PATH.read_text(encoding="utf-8"))["default_sites"]
        assert sorted(sites) == sorted(registers)
        for name, site in sites.items():
            assert site["devices"] == registers[name]

    def test_registers_contract_gives_the_served_addresses(self) -> None:
        """base + offset from the contract = the address the server actually uses."""
        contract = json.loads(REGISTERS_PATH.read_text(encoding="utf-8"))
        site = "2bess_1pv"
        for device in build_layout(default_site(site), POINT_STANDARD):
            entry = next(
                item
                for item in contract["default_sites"][site]
                if (item["kind"], item["asset_id"]) == (device.kind, device.asset_id)
            )
            template = contract["device_types"][device.kind]["registers"]
            addresses = [entry["base"] + register["offset"] for register in template]
            assert addresses == [register.address for register in device.registers]
