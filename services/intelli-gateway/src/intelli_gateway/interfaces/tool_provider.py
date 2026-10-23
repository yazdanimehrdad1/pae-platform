"""The only thing the agent loop talks to for tools. LocalToolProvider implements it today; an
MCPToolProvider would implement the same Protocol."""

from collections.abc import Mapping
from typing import Protocol

from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.tools import ToolResult, ToolSpec


class ToolProvider(Protocol):
    async def list_tools(self) -> list[ToolSpec]: ...

    async def call_tool(
        self, name: str, args: Mapping[str, object], ctx: RequestContext
    ) -> ToolResult: ...
