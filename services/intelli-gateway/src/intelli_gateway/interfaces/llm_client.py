"""The Claude client interface. services/claude implements it; tests fake it."""

from typing import Protocol

from intelli_gateway.schemas.agent import LLMRequest, LLMResponse


class LLMClient(Protocol):
    async def create(self, request: LLMRequest) -> LLMResponse: ...

    async def count_tokens(self, text: str) -> int | None: ...

    async def aclose(self) -> None: ...


class TokenCounter(Protocol):
    async def count_tokens(self, text: str) -> int | None:
        """Token count of `text` as a system prompt, or None if counting is unavailable."""
        ...
