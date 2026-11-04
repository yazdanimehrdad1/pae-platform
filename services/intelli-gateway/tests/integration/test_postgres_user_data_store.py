"""PostgresUserDataStore against a real (throwaway) Postgres: the shared store contract, plus what
the migration adds.

Invariant guarded: the Postgres store passes the same contract as the in-memory one (including
user isolation); the table refuses an unknown axis scale; deleting a user deletes their
preferences, trends and notes.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from user_data_store_contract import ANA, BOB, CHECKS, NOW, trend
from user_store_contract import new_user

from intelli_gateway.interfaces.user_data_store import UserDataStore
from intelli_gateway.services.postgres.database import create_database_engine
from intelli_gateway.services.postgres.user_data_store import PostgresUserDataStore
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
    assert [user.id for user in created] == [ANA, BOB]
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_postgres_user_data_store(
    check: Callable[[UserDataStore], Awaitable[None]], engine: AsyncEngine
) -> None:
    await check(PostgresUserDataStore(engine))


async def test_the_table_refuses_an_unknown_scale(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO user_saved_trends "
                    "(user_id, position, name, points, scale, created_at, updated_at) "
                    "VALUES (:user_id, 0, 'x', '[]', 'log', now(), now())"
                ),
                {"user_id": ANA},
            )


async def test_deleting_a_user_deletes_their_data(engine: AsyncEngine) -> None:
    store = PostgresUserDataStore(engine)
    await store.put_preference(ANA, "last-site", "1001", NOW)
    await store.create_trend(ANA, trend(), NOW)
    await store.create_note(ANA, "note", NOW, NOW)
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": ANA})
    assert await store.list_preferences(ANA) == []
    assert await store.list_trends(ANA) == []
    assert await store.list_notes(ANA) == []
