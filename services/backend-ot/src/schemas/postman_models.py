"""Postman Collection v2.1 models: the subset `make postman` writes (schemas.getpostman.com)."""

from __future__ import annotations

from pydantic import BaseModel, Field

POSTMAN_SCHEMA_URL = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"


class PostmanVariable(BaseModel):
    key: str
    value: str = ""
    description: str | None = None


class PostmanQueryParam(BaseModel):
    key: str
    value: str = ""
    description: str | None = None
    # Optional parameters are listed but switched off, so a request works as imported.
    disabled: bool | None = None


class PostmanHeader(BaseModel):
    key: str
    value: str


class PostmanUrl(BaseModel):
    raw: str
    host: list[str]
    path: list[str]
    query: list[PostmanQueryParam] = Field(default_factory=list)
    variable: list[PostmanVariable] = Field(default_factory=list)


class PostmanRawOptions(BaseModel):
    language: str = "json"


class PostmanBodyOptions(BaseModel):
    raw: PostmanRawOptions = Field(default_factory=PostmanRawOptions)


class PostmanBody(BaseModel):
    mode: str = "raw"
    raw: str
    options: PostmanBodyOptions = Field(default_factory=PostmanBodyOptions)


class PostmanRequest(BaseModel):
    method: str
    url: PostmanUrl
    header: list[PostmanHeader] = Field(default_factory=list)
    body: PostmanBody | None = None
    description: str | None = None


class PostmanItem(BaseModel):
    """A request, or a folder of items."""

    name: str
    request: PostmanRequest | None = None
    item: list[PostmanItem] | None = None


class PostmanInfo(BaseModel):
    name: str
    description: str | None = None
    schema_url: str = Field(POSTMAN_SCHEMA_URL, serialization_alias="schema")


class PostmanCollection(BaseModel):
    info: PostmanInfo
    item: list[PostmanItem]
    variable: list[PostmanVariable] = Field(default_factory=list)
