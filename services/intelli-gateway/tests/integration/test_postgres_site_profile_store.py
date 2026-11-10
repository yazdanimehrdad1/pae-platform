"""PostgresSiteProfileStore against a real (throwaway) Postgres: the shared store contract.

Invariant guarded: the Postgres store passes the same contract as the in-memory one (JSONB round
trip included: enum and bit labels keep their int keys); the table refuses version 0.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from site_profile_store_contract import CHECKS
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from intelli_gateway.interfaces.site_profile_store import SiteProfileStore
from intelli_gateway.services.postgres.database import create_database_engine
from intelli_gateway.services.postgres.site_profile_store import PostgresSiteProfileStore


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
async def test_postgres_site_profile_store(
    check: Callable[[SiteProfileStore], Awaitable[None]], engine: AsyncEngine
) -> None:
    await check(PostgresSiteProfileStore(engine))


async def test_the_table_refuses_version_zero(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO site_profile_versions "
                    "(site_id, version, catalog, approved_at, approved_by) "
                    "VALUES (1, 0, '{}'::jsonb, now(), 'x')"
                )
            )
