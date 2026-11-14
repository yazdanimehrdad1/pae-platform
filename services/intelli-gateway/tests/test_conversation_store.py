"""The in-memory ConversationStore passes the shared store contract (the Postgres one runs the same
checks in tests/integration/test_postgres_conversation_store.py).

Invariant guarded: a conversation keeps its raw history exactly (thinking blocks included) and
its turns in the order asked; a user lists only their own conversations, newest first; feedback
is set and cleared on one turn of one conversation only.
"""

from collections.abc import Awaitable, Callable

import pytest
from conversation_store_contract import CHECKS
from doubles.conversation_store import InMemoryConversationStore

from intelli_gateway.interfaces.conversation_store import ConversationStore


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_in_memory_conversation_store(
    check: Callable[[ConversationStore], Awaitable[None]],
) -> None:
    await check(InMemoryConversationStore())
