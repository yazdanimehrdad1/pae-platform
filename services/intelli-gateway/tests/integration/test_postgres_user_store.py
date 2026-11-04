"""PostgresUserStore against a real (throwaway) Postgres: the shared store contract, plus the
constraints the migration adds.

Invariant guarded: the Postgres store passes the same contract as the in-memory one; the table
refuses a mixed-case email and an unknown role; deleting a user deletes their sessions.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from user_store_contract import CHECKS, NOW, new_user, session

from intelli_gateway.interfaces.user_store import UserStore
from intelli_gateway.services.postgres.database import create_database_engine
from intelli_gateway.services.postgres.user_store import PostgresUserStore


@pytest.fixture
async def engine(
    database_url: str, reset: Callable[[], Awaitable[list[str]]]
) -> AsyncIterator[AsyncEngine]:
    await reset()
    engine = create_database_engine(database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_postgres_user_store(
    check: Callable[[UserStore], Awaitable[None]], engine: AsyncEngine
) -> None:
    await check(PostgresUserStore(engine))


@pytest.mark.parametrize(
    ("email", "role"),
    [("Ana@example.com", "engineer"), ("ana@example.com", "viewer")],
    ids=["mixed-case", "bad-role"],
)
async def test_the_table_refuses_bad_rows(engine: AsyncEngine, email: str, role: str) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO users (email, display_name, password_hash, role) "
                    "VALUES (:email, 'x', 'x', :role)"
                ),
                {"email": email, "role": role},
            )


async def test_deleting_a_user_deletes_their_sessions(engine: AsyncEngine) -> None:
    store = PostgresUserStore(engine)
    user = await store.create_user(new_user(), created_at=NOW)
    await store.create_session(session(user.id))
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    assert await store.get_session("hash-1") is None
