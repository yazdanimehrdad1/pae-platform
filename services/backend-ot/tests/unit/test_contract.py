"""
The published OpenAPI contract matches the app's routes.

Invariant guarded: ``contracts/openapi/backend-ot.openapi.json`` is exactly what
``make contract`` would write now. Change a route, parameter or model without regenerating
it and this fails, so consumers (optimizer, frontend) never build against a stale API.
"""

from pathlib import Path

from app import create_app
from contract import render_openapi_contract

# services/backend-ot/tests/unit/ -> monorepo root (contracts/ is the only shared directory).
CONTRACT_PATH = (
    Path(__file__).resolve().parents[4] / "contracts" / "openapi" / "backend-ot.openapi.json"
)


class TestOpenApiContract:
    def test_committed_contract_is_current(self) -> None:
        assert CONTRACT_PATH.exists(), "missing contract: run `make -C services/backend-ot contract`"
        committed = CONTRACT_PATH.read_bytes().decode("utf-8")
        assert committed == render_openapi_contract(create_app()), (
            "contract is stale: run `make -C services/backend-ot contract` and commit the result"
        )

    def test_rendering_is_deterministic(self) -> None:
        assert render_openapi_contract(create_app()) == render_openapi_contract(create_app())

