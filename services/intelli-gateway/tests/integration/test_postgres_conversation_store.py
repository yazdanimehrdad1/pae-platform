"""PostgresConversationStore against a real (throwaway) Postgres: the shared store contract, plus
what the migration adds.

Invariant guarded: the Postgres store passes the same contract as the in-memory one; a
conversation needs an existing user; a user who asked cannot be deleted out from under their
conversations (they are kept); the table refuses an unknown feedback value.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from conversation_store_contract import ANA, CHECKS, NOW, conversation, turn
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from user_store_contract import new_user

from intelli_gateway.interfaces.conversation_store import ConversationStore
from intelli_gateway.services.postgres.conversation_store import PostgresConversationStore
from intelli_gateway.services.postgres.database import create_database_engine
from intelli_gateway.services.postgres.user_store import PostgresUserStore


@pytest.fixture
async def engine(
    database_url: str, reset: Callable[[], Awaitable[list[str]]]
) -> AsyncIterator[AsyncEngine]:
    await reset()
    engine = create_database_engine(database_url)
    users = PostgresUserStore(engine)
    created = [
        await users.create_user(new_user(name), created_at=NOW)
        for name in ("ana@example.com", "bob@example.com")
    ]
    assert [user.id for user in created] == [1, 2]
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_postgres_conversation_store(
    check: Callable[[ConversationStore], Awaitable[None]], engine: AsyncEngine
) -> None:
    await check(PostgresConversationStore(engine))


async def test_a_conversation_needs_an_existing_user(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError):
        await PostgresConversationStore(engine).save(conversation(user_id=99), turn())


async def test_a_user_with_conversations_is_kept(engine: AsyncEngine) -> None:
    await PostgresConversationStore(engine).save(conversation(), turn())
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": ANA})


async def test_unknown_feedback_is_refused(engine: AsyncEngine) -> None:
    await PostgresConversationStore(engine).save(conversation(), turn())
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE ai_turns SET feedback = 'meh'"))
