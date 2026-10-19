"""
The models in schemas/backend_ot/ match backend-ot's published contract.

Invariant guarded: each strict response model has exactly the fields of the schema of the same
name in contracts/openapi/backend-ot.openapi.json, with the same required set. When backend-ot
regenerates its contract with a changed response, this test fails here, before the strict
models would start rejecting live responses.
"""

import inspect
import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from intelli_gateway.schemas.backend_ot import responses
from intelli_gateway.schemas.backend_ot.responses import StrictModel

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "openapi" / "backend-ot.openapi.json"
)
SCHEMAS: dict[str, dict[str, object]] = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))[
    "components"
]["schemas"]

MODELS = [
    model
    for _, model in inspect.getmembers(responses, inspect.isclass)
    if issubclass(model, StrictModel) and model is not StrictModel
]


def wire_fields(model: type[BaseModel]) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    required: set[str] = set()
    for name, field in model.model_fields.items():
        wire = field.alias or name
        names.add(wire)
        if field.is_required():
            required.add(wire)
    return names, required


def test_every_model_is_checked() -> None:
    assert len(MODELS) >= 20


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__name__)
def test_model_matches_the_contract_schema(model: type[BaseModel]) -> None:
    schema = SCHEMAS.get(model.__name__)
    assert schema is not None, f"{model.__name__} is not in backend-ot's contract"
    properties = set(cast(dict[str, object], schema.get("properties", {})))
    contract_required = set(cast(list[str], schema.get("required", [])))
    names, required = wire_fields(model)
    assert names == properties, (
        f"{model.__name__}: missing {sorted(properties - names)}, "
        f"extra {sorted(names - properties)}"
    )
    assert required == contract_required, (
        f"{model.__name__}: required differs: model {sorted(required)}, "
        f"contract {sorted(contract_required)}"
    )
