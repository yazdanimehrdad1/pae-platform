"""Test doubles for the wrappers this service owns (LLMClient). The anthropic SDK itself is never
mocked: tests fake the wrapper instead."""

import asyncio
import copy
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from intelli_gateway.config import Settings
from intelli_gateway.schemas.agent import ContentBlock, LLMRequest, LLMResponse, LLMUsage
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.tools import JSONValue

FIXED_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)  # midday: PV produces


def fixed_clock() -> datetime:
    return FIXED_NOW


def make_settings(**env: str) -> Settings:
    """Settings from the given env-style values only: tests never read the developer's .env."""
    return Settings(_env_file=None, **env)  # pyright: ignore[reportCallIssue]


def make_ctx(site_id: int | None = 1, site_ids: frozenset[int] | None = None) -> RequestContext:
    return RequestContext(
        user_id="tester",
        roles=frozenset({"engineer"}),
        site_ids=site_ids,
        request_id="test-request",
        site_id=site_id,
    )


def text(answer: str) -> ContentBlock:
    return {"type": "text", "text": answer}


def tool_use(tool_id: str, name: str, args: dict[str, JSONValue]) -> ContentBlock:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": args}


def response(
    *blocks: ContentBlock,
    stop_reason: str = "end_turn",
    usage: LLMUsage | None = None,
    refusal_category: str | None = None,
) -> LLMResponse:
    return LLMResponse(
        content=list(blocks),
        stop_reason=stop_reason,
        usage=usage or LLMUsage(input_tokens=100, output_tokens=10),
        model="claude-test",
        refusal_category=refusal_category,
    )


Step = LLMResponse | Callable[[LLMRequest], LLMResponse]


class ScriptedLLMClient:
    """Returns the scripted responses in order; records a deep copy of every request."""

    def __init__(self, *steps: Step, delay_s: float = 0.0, token_count: int | None = None) -> None:
        self._steps = list(steps)
        self._delay_s = delay_s
        self._token_count = token_count
        self.requests: list[LLMRequest] = []

    async def create(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(copy.deepcopy(request))
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        if not self._steps:
            raise AssertionError("ScriptedLLMClient ran out of scripted responses")
        step = self._steps.pop(0)
        return step(request) if callable(step) else step

    async def count_tokens(self, text: str) -> int | None:
        return self._token_count

    async def aclose(self) -> None:
        return None


Row = dict[str, object]


def as_dict(content: object) -> Row:
    """A tool result's content as a dict (tool results are JSON objects)."""
    assert isinstance(content, dict)
    return cast(Row, content)


def rows(content: object, key: str) -> list[Row]:
    return cast(list[Row], as_dict(content)[key])
