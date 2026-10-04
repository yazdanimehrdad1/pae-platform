"""Write a Postman collection (v2.1) for every powerflow endpoint, generated from the app's
OpenAPI so it can't drift (tests/test_postman.py checks it).

Usage: uv run python scripts/export_postman.py   (or `make postman`)
Output: postman/powerflow.postman_collection.json. Import it in Postman: File → Import.

- Requests are grouped in folders by OpenAPI tag.
- `{{baseUrl}}` (default http://localhost:8020) is a collection variable.
- Path parameters are Postman `:params` with working example values.
- Write requests carry ready-to-send example bodies. The write examples use names that don't
  touch the shipped sites (my_site, my_scenario), except the Modbus map PUT, which re-saves the
  default bess.bess1 map unchanged.
"""

import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from powerflow.app import API_VERSION, create_app  # noqa: E402
from powerflow.storage.seed_data import default_sites  # noqa: E402

OUTPUT = SERVICE_ROOT / "postman" / "powerflow.postman_collection.json"
BASE_URL = "http://localhost:8020"
# Fixed id, so regenerating produces identical bytes (Postman only needs it to be stable).
COLLECTION_ID = "6f1f5c4e-8a53-4c1e-9f44-70f0f10e0001"

EXAMPLE_LOAD_CSV = (
    "timestamp,p_kw,q_kvar\n"
    "2026-06-21T00:00:00Z,800,260\n"
    "2026-06-21T12:00:00Z,1500,490\n"
    "2026-06-21T23:59:00Z,800,260\n"
)


def path_value(method: str, path: str, name: str) -> str:
    """A working example value for a path parameter."""
    if name == "asset_id":
        return {"bess": "bess1", "pv": "pv1", "load": "load1"}[path.split("/")[3]]
    if path.startswith("/api/schemas"):
        return "site-config"
    if path.startswith("/api/points"):
        return "bess.bess1.soc_pct"
    if path.startswith("/api/profiles"):
        writes = method in ("put", "delete")
        return {"folder": "load", "scenario": "my_scenario" if writes else "typical"}[name]
    if name == "asset":
        return "bess.bess1"
    if name == "name" and method in ("put", "delete"):
        return "my_site"
    return "2bess_1pv"


def query_example(name: str) -> tuple[str, bool]:
    """(value, disabled) for a query parameter."""
    examples = {
        "count": ("60", False),
        "overwrite": ("false", False),
        "fields": ("poi.meter.p_kw,bess.bess1.soc_pct", False),
        "format": ("json", False),
        "from": ("2026-06-21T06:00:00Z", True),
        "to": ("2026-06-21T07:00:00Z", True),
    }
    return examples.get(name, ("", True))


def json_body(method: str, path: str) -> object | None:
    if path.endswith("/bess/{asset_id}/setpoint"):
        return {"p_kw": 1500, "q_kvar": 0, "mode": "pq"}
    if path.endswith("/pv/{asset_id}/setpoint"):
        return {"p_limit_pct": 80, "pf": 0.95}
    if method == "put" and path == "/api/sites/{name}":
        site = default_sites()["1bess_1pv"].model_dump(mode="json")
        site["site"]["name"] = "My site (copy of 1bess_1pv)"
        site["simulation"]["autostart"] = False
        return site
    return None


def request_item(method: str, path: str, operation: dict[str, object]) -> dict[str, object]:
    parameters = operation.get("parameters", [])
    assert isinstance(parameters, list)
    postman_path = [
        f":{segment[1:-1]}" if segment.startswith("{") else segment
        for segment in path.strip("/").split("/")
    ]
    path_variables = [
        {"key": parameter["name"], "value": path_value(method, path, parameter["name"])}
        for parameter in parameters
        if parameter["in"] == "path"
    ]
    query = []
    for parameter in parameters:
        if parameter["in"] == "query":
            value, disabled = query_example(parameter["name"])
            entry: dict[str, object] = {"key": parameter["name"], "value": value}
            if disabled:
                entry["disabled"] = True
            query.append(entry)
    raw_url = "{{baseUrl}}/" + "/".join(postman_path)
    if query:
        raw_url += "?" + "&".join(
            f"{entry['key']}={entry['value']}" for entry in query if not entry.get("disabled")
        )
    request: dict[str, object] = {
        "method": method.upper(),
        "header": [],
        "url": {
            "raw": raw_url,
            "host": ["{{baseUrl}}"],
            "path": postman_path,
            **({"query": query} if query else {}),
            **({"variable": path_variables} if path_variables else {}),
        },
    }
    description = str(operation.get("description") or "")
    if description:
        request["description"] = description

    content = operation.get("requestBody", {})
    assert isinstance(content, dict)
    media_types = content.get("content", {})
    if "text/csv" in media_types:
        request["header"] = [{"key": "Content-Type", "value": "text/csv"}]
        request["body"] = {"mode": "raw", "raw": EXAMPLE_LOAD_CSV}
    elif "application/json" in media_types:
        body = json_body(method, path)
        request["header"] = [{"key": "Content-Type", "value": "application/json"}]
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2),
            "options": {"raw": {"language": "json"}},
        }
    return {"name": str(operation.get("summary") or f"{method.upper()} {path}"), "request": request}


def build_collection() -> dict[str, object]:
    spec = create_app().openapi()
    folders: dict[str, list[dict[str, object]]] = {}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            tag = (operation.get("tags") or ["other"])[0]
            folders.setdefault(tag, []).append(request_item(method, path, operation))
    return {
        "info": {
            "_postman_id": COLLECTION_ID,
            "name": f"powerflow {API_VERSION}",
            "description": spec["info"]["description"],
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [{"key": "baseUrl", "value": BASE_URL}],
        "item": [{"name": tag, "item": items} for tag, items in folders.items()],
    }


def render_collection() -> str:
    return json.dumps(build_collection(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(render_collection())
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
