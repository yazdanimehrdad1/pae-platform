"""The committed Postman collection covers every route and matches what the script generates."""

import importlib.util
import json
from types import ModuleType

from conftest import SERVICE_ROOT

from powerflow.app import create_app
from powerflow.core.setpoints import BessSetpointRequest, PvSetpointRequest
from powerflow.profiles import ProfileKind, parse_profile_csv
from powerflow.site_config import SiteConfig


def load_exporter() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "export_postman", SERVICE_ROOT / "scripts" / "export_postman.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collection_is_current() -> None:
    exporter = load_exporter()
    committed = exporter.OUTPUT.read_text(encoding="utf-8")
    assert committed == exporter.render_collection(), "stale: run `make postman`"


def test_every_route_has_a_request() -> None:
    collection = json.loads(load_exporter().render_collection())
    requests = {
        (item["request"]["method"], "/" + "/".join(item["request"]["url"]["path"]))
        for folder in collection["item"]
        for item in folder["item"]
    }
    routes = {
        (
            method.upper(),
            "/"
            + "/".join(
                f":{part[1:-1]}" if part.startswith("{") else part
                for part in path.strip("/").split("/")
            ),
        )
        for path, operations in create_app().openapi()["paths"].items()
        for method in operations
    }
    assert requests == routes


def test_example_bodies_are_valid() -> None:
    """Every example body is accepted by the model its endpoint validates with."""
    models = {
        ("PUT", "setpoint", "bess"): BessSetpointRequest,
        ("PUT", "setpoint", "pv"): PvSetpointRequest,
        ("PUT", ":name", "sites"): SiteConfig,
    }
    collection = json.loads(load_exporter().render_collection())
    checked = 0
    for folder in collection["item"]:
        for item in folder["item"]:
            request = item["request"]
            body = request.get("body")
            if body is None:
                continue
            path = request["url"]["path"]
            if request["header"][0]["value"] == "text/csv":
                parse_profile_csv(body["raw"], ProfileKind.LOAD, loop=True)
            else:
                area = path[2] if path[1] == "assets" else path[1]  # bess/pv or sites
                model = models[(request["method"], path[-1], area)]
                model.model_validate_json(body["raw"])
            checked += 1
    assert checked == 4  # the BESS and PV setpoints, a site, a profile CSV
