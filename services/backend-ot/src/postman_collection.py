"""
A Postman collection of this service's HTTP API, built from its OpenAPI spec.

`make postman` writes it to `postman/backend-ot.postman_collection.json` (import it in Postman:
Import > File). One folder per OpenAPI tag, one request per operation, in spec order. Every URL
starts with `{{baseUrl}}` (a collection variable, default http://localhost:8000); path parameters
are Postman `:variables`; optional query parameters are listed but disabled; JSON bodies are an
example built from the request schema (its examples/defaults, else a placeholder per type).
"""

import json
from collections.abc import Mapping

from fastapi import FastAPI
from pydantic import JsonValue

from schemas.postman_models import (
    PostmanBody,
    PostmanCollection,
    PostmanHeader,
    PostmanInfo,
    PostmanItem,
    PostmanQueryParam,
    PostmanRequest,
    PostmanUrl,
    PostmanVariable,
)

BASE_URL_VARIABLE = "baseUrl"
DEFAULT_BASE_URL = "http://localhost:8000"
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
# Deep enough for every schema here; stops a self-referencing schema from recursing forever.
MAX_EXAMPLE_DEPTH = 10

OpenApi = Mapping[str, JsonValue]


def render_postman_collection(app: FastAPI) -> str:
    """Deterministic JSON text, 2-space indent, trailing newline."""
    collection = build_postman_collection(app.openapi())
    return json.dumps(collection.model_dump(mode="json", by_alias=True, exclude_none=True), indent=2, ensure_ascii=False) + "\n"


def build_postman_collection(spec: OpenApi) -> PostmanCollection:
    info = _mapping(spec.get("info"))
    folders: dict[str, list[PostmanItem]] = {}
    for path, path_item in _mapping(spec.get("paths")).items():
        for method, operation_value in _mapping(path_item).items():
            if method not in HTTP_METHODS:
                continue
            operation = _mapping(operation_value)
            tags = _list(operation.get("tags"))
            folder = str(tags[0]) if tags else "default"
            folders.setdefault(folder, []).append(_request_item(spec, path, method, operation))
    return PostmanCollection(
        info=PostmanInfo(name=str(info.get("title", "API")), description=_optional_str(info.get("description"))),
        item=[PostmanItem(name=folder, item=items) for folder, items in folders.items()],
        variable=[PostmanVariable(key=BASE_URL_VARIABLE, value=DEFAULT_BASE_URL)],
    )


def _request_item(spec: OpenApi, path: str, method: str, operation: Mapping[str, JsonValue]) -> PostmanItem:
    path_segments = [
        f":{segment[1:-1]}" if segment.startswith("{") and segment.endswith("}") else segment
        for segment in path.strip("/").split("/")
    ]
    path_variables: list[PostmanVariable] = []
    query: list[PostmanQueryParam] = []
    for parameter_value in _list(operation.get("parameters")):
        parameter = _mapping(_resolve(spec, parameter_value))
        name = str(parameter.get("name", ""))
        description = _optional_str(parameter.get("description"))
        example = _parameter_value(spec, parameter)
        if parameter.get("in") == "path":
            path_variables.append(PostmanVariable(key=name, value=example, description=description))
        elif parameter.get("in") == "query":
            required = parameter.get("required") is True
            query.append(PostmanQueryParam(key=name, value=example, description=description, disabled=None if required else True))

    raw = "{{" + BASE_URL_VARIABLE + "}}/" + "/".join(path_segments)
    enabled_query = [f"{param.key}={param.value}" for param in query if not param.disabled]
    if enabled_query:
        raw += "?" + "&".join(enabled_query)

    body = _json_body(spec, operation)
    request = PostmanRequest(
        method=method.upper(),
        url=PostmanUrl(raw=raw, host=["{{" + BASE_URL_VARIABLE + "}}"], path=path_segments, query=query, variable=path_variables),
        header=[PostmanHeader(key="Content-Type", value="application/json")] if body else [],
        body=body,
        description=_optional_str(operation.get("description")),
    )
    name = _optional_str(operation.get("summary")) or _optional_str(operation.get("operationId")) or f"{method.upper()} {path}"
    return PostmanItem(name=name, request=request)


def _json_body(spec: OpenApi, operation: Mapping[str, JsonValue]) -> PostmanBody | None:
    request_body = _mapping(_resolve(spec, operation.get("requestBody")))
    json_content = _mapping(_mapping(request_body.get("content")).get("application/json"))
    if "schema" not in json_content:
        return None
    example = _schema_example(spec, json_content["schema"], depth=0)
    return PostmanBody(raw=json.dumps(example, indent=2, ensure_ascii=False))


def _parameter_value(spec: OpenApi, parameter: Mapping[str, JsonValue]) -> str:
    if "example" in parameter:
        return _as_text(parameter["example"])
    schema = _mapping(_resolve(spec, parameter.get("schema")))
    if "default" in schema and schema["default"] is not None:
        return _as_text(schema["default"])
    return ""


def _schema_example(spec: OpenApi, schema_value: JsonValue, depth: int) -> JsonValue:
    """An example value for a schema: its example or default, else a placeholder per type."""
    schema = _mapping(_resolve(spec, schema_value))
    if depth > MAX_EXAMPLE_DEPTH:
        return None
    for key in ("example", "default"):
        if key in schema and schema[key] is not None:
            return schema[key]
    examples = _list(schema.get("examples"))
    if examples:
        return examples[0]
    enum = _list(schema.get("enum"))
    if enum:
        return enum[0]
    if "const" in schema:
        return schema["const"]
    for combinator in ("oneOf", "anyOf", "allOf"):
        options = [option for option in _list(schema.get(combinator)) if _mapping(option).get("type") != "null"]
        if options:
            return _schema_example(spec, options[0], depth + 1)

    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        # Every property with a usable example; an optional one that would be null is left out.
        required = set(_list(schema.get("required")))
        example: dict[str, JsonValue] = {}
        for name, property_schema in _mapping(schema.get("properties")).items():
            value = _schema_example(spec, property_schema, depth + 1)
            if value is not None or name in required:
                example[name] = value
        return example
    if schema_type == "array":
        return [_schema_example(spec, schema.get("items", {}), depth + 1)]
    if schema_type in ("integer", "number"):
        return _lowest_valid_number(schema, integer=schema_type == "integer")
    if schema_type == "boolean":
        return False
    if schema_type == "string":
        return "2026-01-01T00:00:00Z" if schema.get("format") == "date-time" else "string"
    return None


def _lowest_valid_number(schema: Mapping[str, JsonValue], integer: bool) -> int | float:
    """0, or the schema's lower bound when 0 isn't allowed."""
    minimum, exclusive = schema.get("minimum"), schema.get("exclusiveMinimum")
    if isinstance(minimum, int | float) and minimum > 0:
        return int(minimum) if integer else float(minimum)
    if isinstance(exclusive, int | float) and exclusive >= 0:
        return int(exclusive) + 1 if integer else float(exclusive) + 1
    return 0


def _resolve(spec: OpenApi, value: JsonValue) -> JsonValue:
    """Follow a local `$ref` (e.g. #/components/schemas/X), once or repeatedly."""
    seen: set[str] = set()
    while isinstance(value, dict) and isinstance(value.get("$ref"), str):
        reference = str(value["$ref"])
        if reference in seen or not reference.startswith("#/"):
            return {}
        seen.add(reference)
        target: JsonValue = dict(spec)
        for part in reference[2:].split("/"):
            target = _mapping(target).get(part, {})
        value = target
    return value


def _mapping(value: JsonValue | None) -> Mapping[str, JsonValue]:
    return value if isinstance(value, dict) else {}


def _list(value: JsonValue | None) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def _optional_str(value: JsonValue | None) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_text(value: JsonValue) -> str:
    return value if isinstance(value, str) else json.dumps(value)
