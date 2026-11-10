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
from intelli_gateway.services.postgres.database import (
    MIGRATIONS_DIR,
    create_database_engine,
    split_statements,
)
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


async def test_migration_007_renames_stored_site_scripts_to_site_prompts(
    engine: AsyncEngine,
) -> None:
    """Knowledge saved before the rename (`site_scripts`, `script_id`, `script:<id>`) reads back
    as site prompts after 007 runs."""
    old_content = (
        '{"point_guides": [], "documents": [], "device_facts": [], "site_scripts": ['
        '{"script_id": "a1", "site_id": 7, "name": "Overview", "text": "Solar site", '
        '"position": 1, "updated_at": "2026-11-09T10:00:00+00:00"}]}'
    )
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO site_knowledge_versions (site_id, version, content, published_at, "
                "published_by, change_ids) VALUES (7, 1, CAST(:content AS jsonb), now(), 'x', "
                "CAST(:change_ids AS jsonb))"
            ),
            {"content": old_content, "change_ids": '["script:a1", "document:d1"]'},
        )
        await connection.execute(
            text(
                "INSERT INTO site_knowledge_drafts (site_id, revision, content, updated_at, "
                "updated_by) VALUES (7, 1, CAST(:content AS jsonb), now(), 'x')"
            ),
            {"content": old_content},
        )
        sql = (MIGRATIONS_DIR / "007_site_prompts.sql").read_text(encoding="utf-8")
        for statement in split_statements(sql):
            await connection.exec_driver_sql(statement)

    store = PostgresKnowledgeAuthoringStore(engine)
    version = await store.get_version(7, 1)
    draft = await store.get_draft(7)
    assert version is not None and draft is not None
    for content in (version.content, draft.content):
        assert [(p.prompt_id, p.name, p.position) for p in content.site_prompts] == [
            ("a1", "Overview", 1)
        ]
    assert version.change_ids == ("prompt:a1", "document:d1")
