"""In-process ToolProvider: validates input, authorizes, runs the tool, never raises to the loop."""

import logging
import time
from collections.abc import Mapping, Sequence

from pydantic import ValidationError

from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.tools import JSONValue, ToolResult, ToolSpec
from intelli_gateway.tools import authz
from intelli_gateway.tools.base import ToolDefinition, ToolError
from intelli_gateway.tools.bounds import bound_output, serialized_size
from intelli_gateway.utils.telemetry import span

logger = logging.getLogger(__name__)


class LocalToolProvider:
    def __init__(self, tools: Sequence[ToolDefinition], max_output_chars: int) -> None:
        by_name: dict[str, ToolDefinition] = {}
        for definition in tools:
            if definition.spec.name in by_name:
                raise ValueError(f"duplicate tool name: {definition.spec.name}")
            by_name[definition.spec.name] = definition
        self._tools = by_name
        self._max_output_chars = max_output_chars

    async def list_tools(self) -> list[ToolSpec]:
        # Sorted, so the tool list is byte-identical between requests (prompt cache prefix).
        return [self._tools[name].spec for name in sorted(self._tools)]

    async def call_tool(
        self, name: str, args: Mapping[str, object], ctx: RequestContext
    ) -> ToolResult:
        started = time.perf_counter()
        result = await self._run(name, args, ctx)
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "tool_call",
            extra={
                "fields": {
                    "user_id": ctx.user_id,
                    "site_id": ctx.site_id,
                    "tool": name,
                    "args": dict(args),
                    "duration_ms": round(duration_ms, 1),
                    "ok": not result.is_error,
                    "result_chars": serialized_size(result.content),
                }
            },
        )
        return result

    async def _run(self, name: str, args: Mapping[str, object], ctx: RequestContext) -> ToolResult:
        definition = self._tools.get(name)
        if definition is None:
            return ToolResult(
                content={"error": f"unknown tool: {name}", "hint": "use one of the listed tools"},
                is_error=True,
            )
        try:
            validated = definition.input_model.model_validate(dict(args))
        except ValidationError as error:
            details: list[JSONValue] = [
                {"field": ".".join(str(part) for part in issue["loc"]), "problem": issue["msg"]}
                for issue in error.errors()
            ]
            return ToolResult(
                content={"error": "invalid arguments", "details": details}, is_error=True
            )
        try:
            authz.check(ctx, name)
            with span("tool_call", tool=name, site_id=ctx.site_id):
                content = await definition.handler(validated, ctx)
        except ToolError as error:
            return ToolResult(content=error.to_content(), is_error=True)
        except Exception:
            # Unexpected: log it with the traceback, give Claude a generic error result.
            logger.exception("tool_failed", extra={"fields": {"tool": name}})
            return ToolResult(
                content={"error": "internal error while running the tool"}, is_error=True
            )
        return ToolResult(content=bound_output(content, self._max_output_chars))
