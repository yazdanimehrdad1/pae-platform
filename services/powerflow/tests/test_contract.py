"""
The published contracts match the code.

Invariant guarded: ``contracts/openapi/powerflow.openapi.json`` and
``contracts/powerflow/points.json`` are exactly what ``make contract`` would write now, so
consumers never build against a stale API or point list.
"""

from pathlib import Path

from powerflow.app import create_app
from powerflow.contract import render_openapi_contract, render_points_contract

# services/powerflow/tests/ -> monorepo root (contracts/ is the only shared directory).
CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
OPENAPI_PATH = CONTRACTS_DIR / "openapi" / "powerflow.openapi.json"
POINTS_PATH = CONTRACTS_DIR / "powerflow" / "points.json"
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
