"""Real Claude API calls (cost tokens). Skipped unless RUN_LLM_TESTS=1 and a credential is set
(ANTHROPIC_API_KEY in the environment or this service's .env). Run: `make test-integration`."""

import os

import pytest
from fakes import fixed_clock

from intelli_gateway.config import load_settings
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.services.claude.client import AnthropicLLMClient
from intelli_gateway.wiring import build_services

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LLM_TESTS") != "1", reason="set RUN_LLM_TESTS=1 to call the real Claude API"
)


async def test_tool_use_and_prompt_caching_against_the_real_api() -> None:
    settings = load_settings()
    llm = AnthropicLLMClient(settings)
    services = build_services(settings, llm=llm, clock=fixed_clock)
    ctx = RequestContext(
        user_id="integration", roles=frozenset({"engineer"}), site_ids=None, request_id="it"
    )
    try:
        first = await services.gateway.ask(
            ctx, 1, "What is the current state code of INV2, and what does it mean?", None
        )
        assert first.result.stop_reason == "end_turn", first.result.answer
        assert any(
            call.name in {"get_point_value", "list_points"} for call in first.result.tool_calls
        )
        assert first.result.answer

        second = await services.gateway.ask(
            ctx, 1, "Is its cabinet hotter than INV1's right now?", first.conversation_id
        )
        assert second.result.stop_reason == "end_turn", second.result.answer
        # The site knowledge and the earlier turns are served from the prompt cache.
        assert second.result.usage.cache_read_input_tokens > 0
    finally:
        await services.aclose()
