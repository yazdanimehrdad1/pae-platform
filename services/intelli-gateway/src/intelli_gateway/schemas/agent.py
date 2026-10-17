"""Provider-neutral shapes the agent loop uses. Message content blocks follow the Messages API
format (text, thinking, tool_use, tool_result), which Claude on Bedrock/Vertex/Foundry shares."""

from dataclasses import dataclass, field
from typing import Literal, TypedDict

from intelli_gateway.schemas.tools import JSONValue, ToolSpec

ContentBlock = dict[str, JSONValue]


class ChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: list[ContentBlock]


@dataclass(frozen=True)
class SystemBlock:
    text: str
    # Mark the end of a stable prefix for prompt caching.
    cache: bool = False


@dataclass(frozen=True)
class LLMRequest:
    system: list[SystemBlock]
    tools: list[ToolSpec]
    messages: list[ChatMessage]


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def __add__(self, other: "LLMUsage") -> "LLMUsage":
        return LLMUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens + other.cache_read_input_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens
            + other.cache_creation_input_tokens,
        )


@dataclass(frozen=True)
class LLMResponse:
    # Ready to append to the conversation as the assistant turn, unchanged.
    content: list[ContentBlock]
    stop_reason: str
    usage: LLMUsage
    model: str
    refusal_category: str | None = None


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    args: dict[str, JSONValue]
    summary: str
    duration_ms: float
    is_error: bool


@dataclass(frozen=True)
class AgentResult:
    answer: str
    # end_turn, max_tokens, refusal, max_iterations, timeout, ...
    stop_reason: str
    iterations: int
    tool_calls: list[ToolCallRecord]
    usage: LLMUsage
    model: str | None
    # The full conversation after this turn, to store.
    messages: list[ChatMessage] = field(repr=False)
    refusal_category: str | None = None


@dataclass
class Conversation:
    conversation_id: str
    user_id: str
    site_id: int
    messages: list[ChatMessage] = field(default_factory=lambda: list[ChatMessage]())
