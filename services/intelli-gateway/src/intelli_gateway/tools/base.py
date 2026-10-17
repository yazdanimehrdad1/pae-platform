"""Declaring local tools: the @tool decorator, ToolDefinition and ToolError. The shapes (ToolSpec,
ToolResult, ToolInput) are in schemas/tools.py; the ToolProvider Protocol is in
interfaces/tool_provider.py."""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.tools import JSONValue, ToolInput, ToolSpec

# Pydantic's recursive JSON type: usable in models (schemas) and understood by pyright.

TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ToolError(Exception):
    """Raised by a tool for an expected failure. The provider turns it into an error result."""

    def __init__(self, error: str, hint: str | None = None) -> None:
        super().__init__(error)
        self.error = error
        self.hint = hint

    def to_content(self) -> dict[str, JSONValue]:
        content: dict[str, JSONValue] = {"error": self.error}
        if self.hint:
            content["hint"] = self.hint
        return content


InputT = TypeVar("InputT", bound=ToolInput)
ToolHandler = Callable[[InputT, RequestContext], Awaitable[JSONValue]]


@dataclass(frozen=True)
class ToolDefinition:
    """A local tool: its spec, its input model, and the function that runs it on validated input."""

    spec: ToolSpec
    input_model: type[ToolInput]
    handler: Callable[[ToolInput, RequestContext], Awaitable[JSONValue]]


def tool(
    *, name: str, description: str, input_model: type[InputT]
) -> Callable[[ToolHandler[InputT]], ToolDefinition]:
    """Declare a tool. The description is written for Claude: what it does, when to use it,
    and what it returns."""
    if not TOOL_NAME_PATTERN.match(name):
        raise ValueError(f"tool name must be snake_case: {name!r}")

    def decorate(handler: ToolHandler[InputT]) -> ToolDefinition:
        async def run(validated: ToolInput, ctx: RequestContext) -> JSONValue:
            if not isinstance(validated, input_model):
                raise TypeError(f"{name} expects {input_model.__name__}")
            return await handler(validated, ctx)

        spec = ToolSpec(
            name=name,
            description=description.strip(),
            input_schema=input_model.model_json_schema(),
        )
        return ToolDefinition(spec=spec, input_model=input_model, handler=run)

    return decorate
