"""
The published OpenAPI contract matches the app's routes.

Invariant guarded: ``contracts/openapi/intelli-gateway.openapi.json`` is exactly what
``make contract`` would write now, so consumers never build against a stale API.
"""

from pathlib import Path

from intelli_gateway.app import create_app
from intelli_gateway.contract import render_openapi_contract

# services/intelli-gateway/tests/ -> monorepo root (contracts/ is the only shared directory).
CONTRACT_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "openapi" / "intelli-gateway.openapi.json"
)


class TestOpenApiContract:
    def test_committed_contract_is_current(self) -> None:
        assert CONTRACT_PATH.exists(), (
            "missing contract: run `make -C services/intelli-gateway contract`"
        )
        committed = CONTRACT_PATH.read_bytes().decode("utf-8")
        assert committed == render_openapi_contract(create_app()), (
            "contract is stale: run `make -C services/intelli-gateway contract` "
            "and commit the result"
        )
