"""Tool shapes, mirroring MCP: a tool listing (ToolSpec), a call result (ToolResult), and the
base of every tool's input model."""

from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, JsonValue

JSONValue: TypeAlias = JsonValue


class ToolSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, JSONValue]


class ToolResult(BaseModel):
    content: JSONValue
    is_error: bool = False


class ToolInput(BaseModel):
    """Base class for tool input models: unknown fields are rejected, not silently dropped."""

    model_config = ConfigDict(extra="forbid")
