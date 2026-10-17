"""Conversation history store: in memory for v1, Postgres or Redis later."""

from typing import Protocol

from intelli_gateway.schemas.agent import Conversation


class ConversationStore(Protocol):
    async def get(self, conversation_id: str) -> Conversation | None: ...

    async def save(self, conversation: Conversation) -> None: ...
