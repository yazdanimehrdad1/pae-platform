"""PostgresKnowledgeAuthoringStore against a real (throwaway) Postgres: the shared store contract.

Invariant guarded: the Postgres store passes the same contract as the in-memory one (the JSONB
round trip keeps every guide, state, document and rating); the tables refuse revision and
version 0.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from knowledge_authoring_store_contract import CHECKS
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from intelli_gateway.interfaces.knowledge_authoring_store import KnowledgeAuthoringStore
from intelli_gateway.services.postgres.database import create_database_engine
from intelli_gateway.services.postgres.knowledge_authoring_store import (
    PostgresKnowledgeAuthoringStore,
)


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
async def test_postgres_knowledge_authoring_store(
    check: Callable[[KnowledgeAuthoringStore], Awaitable[None]], engine: AsyncEngine
) -> None:
    await check(PostgresKnowledgeAuthoringStore(engine))


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO site_knowledge_drafts (site_id, revision, content, updated_at, updated_by) "
        "VALUES (1, 0, '{}'::jsonb, now(), 'x')",
        "INSERT INTO site_knowledge_versions (site_id, version, content, published_at, "
        "published_by) VALUES (1, 0, '{}'::jsonb, now(), 'x')",
    ],
    ids=["draft-revision-0", "version-0"],
)
async def test_the_tables_refuse_number_zero(engine: AsyncEngine, statement: str) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(text(statement))
