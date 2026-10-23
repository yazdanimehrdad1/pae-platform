"""In-memory conversation store (v1). Implements interfaces/conversation_store.py; a Postgres or
Redis store would replace it."""

import asyncio
from collections import OrderedDict

from intelli_gateway.schemas.agent import Conversation


class InMemoryConversationStore:
    """Process-local, lost on restart. Keeps the most recently saved `max_conversations`."""

    def __init__(self, max_conversations: int = 1000) -> None:
        self._conversations: OrderedDict[str, Conversation] = OrderedDict()
        self._max = max_conversations
        self._lock = asyncio.Lock()

    async def get(self, conversation_id: str) -> Conversation | None:
        async with self._lock:
            return self._conversations.get(conversation_id)

    async def save(self, conversation: Conversation) -> None:
        async with self._lock:
            self._conversations[conversation.conversation_id] = conversation
            self._conversations.move_to_end(conversation.conversation_id)
            while len(self._conversations) > self._max:
                self._conversations.popitem(last=False)
