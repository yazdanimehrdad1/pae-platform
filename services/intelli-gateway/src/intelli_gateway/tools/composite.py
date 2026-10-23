"""Combine several ToolProviders (e.g. local tools plus a future MCP server) behind one."""

from collections.abc import Mapping, Sequence

from intelli_gateway.interfaces.tool_provider import ToolProvider
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.tools import ToolResult, ToolSpec


class CompositeToolProvider:
    def __init__(self, providers: Sequence[ToolProvider]) -> None:
        self._providers = list(providers)

    async def list_tools(self) -> list[ToolSpec]:
        specs: dict[str, ToolSpec] = {}
        for provider in self._providers:
            for spec in await provider.list_tools():
                if spec.name in specs:
                    raise ValueError(f"tool {spec.name!r} is provided twice")
                specs[spec.name] = spec
        return [specs[name] for name in sorted(specs)]

    async def call_tool(
        self, name: str, args: Mapping[str, object], ctx: RequestContext
    ) -> ToolResult:
        for provider in self._providers:
            if any(spec.name == name for spec in await provider.list_tools()):
                return await provider.call_tool(name, args, ctx)
        return ToolResult(
            content={"error": f"unknown tool: {name}", "hint": "use one of the listed tools"},
            is_error=True,
        )
