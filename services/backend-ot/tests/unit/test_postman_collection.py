"""Unit tests for postman_collection (the `make postman` export).

Invariants guarded: every operation in the app's OpenAPI spec becomes exactly one Postman request,
filed under its tag; URLs start with {{baseUrl}} and turn {path} params into :variables; optional
query params are listed but disabled; JSON bodies are examples built from the request schema,
following $refs, preferring schema examples, and leaving out optional fields that would be null.
"""

import json

from app import app
from postman_collection import BASE_URL_VARIABLE, build_postman_collection
from schemas.postman_models import POSTMAN_SCHEMA_URL, PostmanItem

SPEC = {
    "info": {"title": "Demo API", "description": "demo"},
    "paths": {
        "/api/sites/{site_id}/things": {
            "parameters": [],
            "get": {
                "tags": ["things"],
                "summary": "List things",
                "parameters": [
                    {"name": "site_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "default": 10}},
                    {"name": "kind", "in": "query", "required": True, "example": "a", "schema": {"type": "string"}},
                ],
            },
            "post": {
                "tags": ["things"],
                "operationId": "create_thing",
                "requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Thing"}}}},
            },
        },
    },
    "components": {"schemas": {
        "Thing": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "size": {"type": "integer", "minimum": 1},
                "ratio": {"type": "number", "exclusiveMinimum": 0},
                "kind": {"enum": ["small", "big"]},
                "note": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                "part": {"$ref": "#/components/schemas/Part"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "legacy": {"description": "no type, no example: left out"},
            },
        },
        "Part": {"type": "object", "examples": [{"id": 7}], "properties": {"id": {"type": "integer"}}},
    }},
}


def requests_by_name(items: list[PostmanItem]) -> dict[str, PostmanItem]:
    return {request.name: request for folder in items for request in folder.item or []}


class TestBuildPostmanCollection:
    def test_collection_info_and_base_url_variable(self):
        collection = build_postman_collection(SPEC)
        assert (collection.info.name, collection.info.schema_url) == ("Demo API", POSTMAN_SCHEMA_URL)
        assert [(variable.key, variable.value) for variable in collection.variable] == [(BASE_URL_VARIABLE, "http://localhost:8000")]

    def test_one_folder_per_tag_and_names_from_summary_or_operation_id(self):
        collection = build_postman_collection(SPEC)
        assert [folder.name for folder in collection.item] == ["things"]
        assert list(requests_by_name(collection.item)) == ["List things", "create_thing"]

    def test_url_uses_base_url_path_variables_and_disables_optional_query(self):
        request = requests_by_name(build_postman_collection(SPEC).item)["List things"].request
        assert request is not None
        assert request.url.raw == "{{baseUrl}}/api/sites/:site_id/things?kind=a"
        assert request.url.path == ["api", "sites", ":site_id", "things"]
        assert [variable.key for variable in request.url.variable] == ["site_id"]
        assert [(param.key, param.value, param.disabled) for param in request.url.query] == [("limit", "10", True), ("kind", "a", None)]
        assert request.body is None and request.header == []

    def test_json_body_is_an_example_of_the_request_schema(self):
        request = requests_by_name(build_postman_collection(SPEC).item)["create_thing"].request
        assert request is not None and request.body is not None
        assert request.method == "POST"
        assert [header.key for header in request.header] == ["Content-Type"]
        assert json.loads(request.body.raw) == {
            "name": "string", "size": 1, "ratio": 1.0, "kind": "small", "note": "string", "part": {"id": 7},
            "tags": ["string"],
        }


class TestRealApp:
    def test_every_operation_of_the_app_is_a_request(self):
        spec = app.openapi()
        operations = sum(
            1 for path_item in spec["paths"].values() for method in path_item if method in ("get", "post", "put", "patch", "delete")
        )
        collection = build_postman_collection(spec)
        assert sum(len(folder.item or []) for folder in collection.item) == operations
        create_virtual = requests_by_name(collection.item)["Create a virtual point"].request
        assert create_virtual is not None
        assert create_virtual.url.raw == "{{baseUrl}}/api/device-points/site/:site_id/device/:device_id/virtual"
