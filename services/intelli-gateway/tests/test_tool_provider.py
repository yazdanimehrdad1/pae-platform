"""The provider's guarantees: validated input, authorization on every call, errors returned as
results (never raised), bounded output, a stable tool list."""

from typing import cast

import pytest
from fakes import make_ctx
from pydantic import Field

from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.tools import JSONValue, ToolInput, ToolSpec
from intelli_gateway.tools import authz
from intelli_gateway.tools.base import ToolError, tool
from intelli_gateway.tools.composite import CompositeToolProvider
from intelli_gateway.tools.local_provider import LocalToolProvider


class EchoInput(ToolInput):
    size: int = Field(default=1, ge=1)


@tool(name="echo", description="Echo a payload of the given size.", input_model=EchoInput)
async def echo(args: EchoInput, ctx: RequestContext) -> JSONValue:
    return {"site_id": ctx.site_id, "payload": "x" * args.size}


@tool(name="boom", description="Always fails unexpectedly.", input_model=ToolInput)
async def boom(args: ToolInput, ctx: RequestContext) -> JSONValue:
    raise RuntimeError("secret internal detail")


@tool(name="expected_failure", description="Fails with a hint.", input_model=ToolInput)
async def expected_failure(args: ToolInput, ctx: RequestContext) -> JSONValue:
    raise ToolError("nothing here", hint="try something else")


def make_provider(max_output_chars: int = 1000) -> LocalToolProvider:
    return LocalToolProvider([echo, boom, expected_failure], max_output_chars=max_output_chars)


class TestToolDeclaration:
    def test_rejects_non_snake_case_names(self) -> None:
        with pytest.raises(ValueError):
            tool(name="ListPoints", description="x", input_model=ToolInput)

    def test_spec_has_json_schema_from_the_input_model(self) -> None:
        properties = cast(dict[str, object], echo.spec.input_schema["properties"])
        assert "size" in properties
        assert echo.spec.input_schema["additionalProperties"] is False

    def test_duplicate_names_are_rejected(self) -> None:
        with pytest.raises(ValueError):
            LocalToolProvider([echo, echo], max_output_chars=100)


class TestCallTool:
    async def test_list_tools_is_sorted(self) -> None:
        names = [spec.name for spec in await make_provider().list_tools()]
        assert names == sorted(names)

    async def test_success(self) -> None:
        result = await make_provider().call_tool("echo", {"size": 3}, make_ctx(site_id=7))
        assert result.content == {"site_id": 7, "payload": "xxx"}
        assert not result.is_error

    async def test_unknown_tool(self) -> None:
        result = await make_provider().call_tool("nope", {}, make_ctx())
        assert result.is_error

    async def test_invalid_arguments_are_reported_per_field(self) -> None:
        result = await make_provider().call_tool("echo", {"size": 0}, make_ctx())
        assert result.is_error
        content = cast(dict[str, object], result.content)
        assert content["error"] == "invalid arguments"
        assert cast(list[dict[str, object]], content["details"])[0]["field"] == "size"

    async def test_unknown_arguments_are_rejected(self) -> None:
        result = await make_provider().call_tool("echo", {"site_id": 2}, make_ctx())
        assert result.is_error

    async def test_unexpected_exception_becomes_generic_error(self) -> None:
        result = await make_provider().call_tool("boom", {}, make_ctx())
        assert result.is_error
        assert "secret" not in str(result.content)

    async def test_tool_error_keeps_its_hint(self) -> None:
        result = await make_provider().call_tool("expected_failure", {}, make_ctx())
        assert result.content == {"error": "nothing here", "hint": "try something else"}

    async def test_large_output_is_truncated(self) -> None:
        result = await make_provider(max_output_chars=100).call_tool(
            "echo", {"size": 500}, make_ctx()
        )
        content = cast(dict[str, object], result.content)
        assert content["truncated"] is True
        assert len(cast(str, content["preview"])) == 100


class TestAuthorization:
    async def test_every_call_is_checked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        checked: list[str] = []
        monkeypatch.setattr(authz, "check", lambda ctx, name: checked.append(name))
        await make_provider().call_tool("echo", {}, make_ctx())
        assert checked == ["echo"]

    async def test_call_without_site_is_rejected(self) -> None:
        result = await make_provider().call_tool("echo", {}, make_ctx(site_id=None))
        assert result.is_error

    async def test_call_for_a_site_outside_the_users_access_is_rejected(self) -> None:
        result = await make_provider().call_tool(
            "echo", {}, make_ctx(site_id=2, site_ids=frozenset({1}))
        )
        assert result.is_error
        assert result.content == {"error": "access to this site is not allowed"}


class TestCompositeToolProvider:
    async def test_routes_calls_to_the_owning_provider(self) -> None:
        composite = CompositeToolProvider(
            [
                LocalToolProvider([echo], max_output_chars=100),
                LocalToolProvider([expected_failure], max_output_chars=100),
            ]
        )
        assert [spec.name for spec in await composite.list_tools()] == ["echo", "expected_failure"]
        result = await composite.call_tool("expected_failure", {}, make_ctx())
        assert result.content == {"error": "nothing here", "hint": "try something else"}

    async def test_duplicate_tool_across_providers_is_an_error(self) -> None:
        composite = CompositeToolProvider(
            [LocalToolProvider([echo], 100), LocalToolProvider([echo], 100)]
        )
        with pytest.raises(ValueError):
            await composite.list_tools()

    def test_spec_is_immutable(self) -> None:
        assert isinstance(echo.spec, ToolSpec)
        with pytest.raises(ValueError):
            echo.spec.name = "changed"
