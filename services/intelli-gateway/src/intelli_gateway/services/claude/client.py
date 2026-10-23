"""The only module that imports `anthropic`. Every Claude call goes through AnthropicLLMClient.

Switching to Claude on a cloud provider (Bedrock / Vertex / Foundry) means changing this
module only: the client class, the model id format, and the refusal fallback (server-side
`fallbacks` is Claude API only; the providers need the SDK's client-side middleware instead).
"""

import logging
from typing import cast

import anthropic
from anthropic.types.beta import (
    BetaMessage,
    BetaMessageParam,
    BetaTextBlockParam,
    BetaToolParam,
)

from intelli_gateway.config import Settings
from intelli_gateway.schemas.agent import ContentBlock, LLMRequest, LLMResponse, LLMUsage
from intelli_gateway.schemas.tools import JSONValue
from intelli_gateway.utils.exceptions import LLMUnavailableError

logger = logging.getLogger(__name__)

# `fallbacks: "default"` lets the API re-run a declined request on Anthropic's recommended
# fallback model, routed by refusal category.
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Block types that may precede a mid-output `fallback` block and are kept when echoing it back.
_ECHOABLE_BEFORE_FALLBACK = frozenset({"text"})


def echo_content(blocks: list[ContentBlock]) -> list[ContentBlock]:
    """The assistant content to append to the conversation, unchanged except after a mid-output
    refusal fallback: there, only text blocks before the last `fallback` marker are echoed
    (the declined model's thinking and tool_use blocks are dropped) and the marker is dropped."""
    boundary = max(
        (index for index, block in enumerate(blocks) if block.get("type") == "fallback"),
        default=None,
    )
    if boundary is None:
        return blocks
    before = [
        block for block in blocks[:boundary] if block.get("type") in _ECHOABLE_BEFORE_FALLBACK
    ]
    return before + blocks[boundary + 1 :]


def _usage(message: BetaMessage) -> LLMUsage:
    usage = message.usage
    return LLMUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_input_tokens=usage.cache_read_input_tokens or 0,
        cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
    )


class AnthropicLLMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        api_key = (
            settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        )
        # api_key None: the SDK resolves other credential sources (ANTHROPIC_AUTH_TOKEN,
        # `ant auth login` profiles). Missing credentials only fail on the first request.
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key, timeout=settings.claude_request_timeout_s, max_retries=2
        )

    async def create(self, request: LLMRequest) -> LLMResponse:
        settings = self._settings
        system: list[BetaTextBlockParam] = []
        for block in request.system:
            param: BetaTextBlockParam = {"type": "text", "text": block.text}
            if block.cache:
                param["cache_control"] = {"type": "ephemeral"}
            system.append(param)
        tools: list[BetaToolParam] = [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": cast("dict[str, object]", spec.input_schema),  # pyright: ignore[reportAssignmentType]
            }
            for spec in request.tools
        ]
        # Our ChatMessage dicts are Messages-API content blocks; the SDK's TypedDicts describe
        # the same JSON.
        messages = cast("list[BetaMessageParam]", request.messages)
        try:
            # Streaming avoids HTTP timeouts on long outputs; we only need the final message.
            if settings.claude_refusal_fallback:
                stream_manager = self._client.beta.messages.stream(
                    model=settings.claude_model,
                    max_tokens=settings.claude_max_tokens,
                    system=system,
                    tools=tools,
                    messages=messages,
                    thinking={"type": "adaptive"},
                    output_config={"effort": settings.claude_effort},
                    # Top-level automatic caching: also caches the growing conversation.
                    cache_control={"type": "ephemeral"},
                    betas=[REFUSAL_FALLBACK_BETA],
                    fallbacks="default",
                )
            else:
                stream_manager = self._client.beta.messages.stream(
                    model=settings.claude_model,
                    max_tokens=settings.claude_max_tokens,
                    system=system,
                    tools=tools,
                    messages=messages,
                    thinking={"type": "adaptive"},
                    output_config={"effort": settings.claude_effort},
                    cache_control={"type": "ephemeral"},
                )
            async with stream_manager as stream:
                message = await stream.get_final_message()
        except (anthropic.RateLimitError, anthropic.OverloadedError) as error:
            raise LLMUnavailableError(
                f"Claude is busy ({error.status_code}); retry later"
            ) from error
        except anthropic.AuthenticationError as error:
            raise LLMUnavailableError("Claude rejected the API credentials") from error
        except anthropic.APIStatusError as error:
            logger.error(
                "claude_api_error",
                extra={"fields": {"status": error.status_code, "detail": str(error)[:500]}},
            )
            raise LLMUnavailableError(f"Claude API error ({error.status_code})") from error
        except anthropic.APIConnectionError as error:
            raise LLMUnavailableError("could not reach the Claude API") from error
        except TypeError as error:
            # The SDK raises TypeError when no credential source resolves.
            raise LLMUnavailableError(
                "Claude credentials are not configured (set ANTHROPIC_API_KEY)"
            ) from error

        content: list[ContentBlock] = [
            cast("dict[str, JSONValue]", block.model_dump(mode="json", exclude_none=True))
            for block in message.content
        ]
        refusal_category: str | None = None
        if message.stop_reason == "refusal" and message.stop_details is not None:
            refusal_category = message.stop_details.category
        return LLMResponse(
            content=echo_content(content),
            stop_reason=message.stop_reason or "unknown",
            usage=_usage(message),
            model=message.model,
            refusal_category=refusal_category,
        )

    async def count_tokens(self, text: str) -> int | None:
        try:
            result = await self._client.beta.messages.count_tokens(
                model=self._settings.claude_model,
                system=[{"type": "text", "text": text}],
                messages=[{"role": "user", "content": "."}],
            )
        except (anthropic.AnthropicError, TypeError) as error:
            # Counting is only for the size log; fall back to an estimate.
            logger.warning(
                "count_tokens_unavailable", extra={"fields": {"reason": type(error).__name__}}
            )
            return None
        return result.input_tokens

    async def aclose(self) -> None:
        await self._client.close()
