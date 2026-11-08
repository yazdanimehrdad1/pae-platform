"""PostgresKnowledgeAuthoringStore: knowledge drafts and published versions in this service's
Postgres (SQLAlchemy 2 Core over asyncpg). Tables: migration 006_knowledge."""

from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from intelli_gateway.schemas.knowledge import KnowledgeDraft, KnowledgeVersion
from intelli_gateway.utils.exceptions import ConflictError

metadata = MetaData()
drafts_table = Table(
    "site_knowledge_drafts",
    metadata,
    Column("site_id", BigInteger(), primary_key=True),
    Column("revision", Integer(), nullable=False),
    Column("content", JSONB(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("updated_by", Text(), nullable=False),
)
versions_table = Table(
    "site_knowledge_versions",
    metadata,
    Column("site_id", BigInteger(), primary_key=True),
    Column("version", Integer(), primary_key=True),
    Column("content", JSONB(), nullable=False),
    Column("published_at", DateTime(timezone=True), nullable=False),
    Column("published_by", Text(), nullable=False),
    Column("change_ids", JSONB(), nullable=False),
    Column("restored_from", Integer()),
)

DRAFT_CHANGED = "the draft was changed by someone else since; reload it and try again"


def _draft(row: RowMapping) -> KnowledgeDraft:
    return KnowledgeDraft.model_validate(dict(row))


def _version(row: RowMapping) -> KnowledgeVersion:
    return KnowledgeVersion.model_validate(dict(row))


async def _draft_revision(connection: AsyncConnection, site_id: int) -> int | None:
    result = await connection.execute(
        select(drafts_table.c.revision).where(drafts_table.c.site_id == site_id).with_for_update()
    )
    return result.scalar_one_or_none()


class PostgresKnowledgeAuthoringStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get_draft(self, site_id: int) -> KnowledgeDraft | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(drafts_table).where(drafts_table.c.site_id == site_id)
            )
            row = result.mappings().one_or_none()
        return _draft(row) if row is not None else None

    async def save_draft(self, draft: KnowledgeDraft) -> None:
        values: dict[str, Any] = {
            "site_id": draft.site_id,
            "revision": draft.revision,
            "content": draft.content.model_dump(mode="json"),
            "updated_at": draft.updated_at,
            "updated_by": draft.updated_by,
        }
        try:
            async with self._engine.begin() as connection:
                stored = await _draft_revision(connection, draft.site_id)
                if (stored or 0) + 1 != draft.revision:
                    raise ConflictError(DRAFT_CHANGED)
                if stored is None:
                    await connection.execute(insert(drafts_table).values(values))
                else:
                    await connection.execute(
                        update(drafts_table)
                        .where(drafts_table.c.site_id == draft.site_id)
                        .values(values)
                    )
        except IntegrityError as error:  # two first saves at once
            raise ConflictError(DRAFT_CHANGED) from error

    async def delete_draft(self, site_id: int) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(delete(drafts_table).where(drafts_table.c.site_id == site_id))

    async def get_version(
        self, site_id: int, version: int | None = None
    ) -> KnowledgeVersion | None:
        query = select(versions_table).where(versions_table.c.site_id == site_id)
        if version is None:
            query = query.order_by(versions_table.c.version.desc()).limit(1)
        else:
            query = query.where(versions_table.c.version == version)
        async with self._engine.connect() as connection:
            row = (await connection.execute(query)).mappings().one_or_none()
        return _version(row) if row is not None else None

    async def list_versions(self, site_id: int) -> list[KnowledgeVersion]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(versions_table)
                .where(versions_table.c.site_id == site_id)
                .order_by(versions_table.c.version.desc())
            )
            return [_version(row) for row in result.mappings()]

    async def publish(self, version: KnowledgeVersion, draft_revision: int | None) -> None:
        values: dict[str, Any] = {
            "site_id": version.site_id,
            "version": version.version,
            "content": version.content.model_dump(mode="json"),
            "published_at": version.published_at,
            "published_by": version.published_by,
            "change_ids": list(version.change_ids),
            "restored_from": version.restored_from,
        }
        try:
            async with self._engine.begin() as connection:
                if draft_revision is not None:
                    stored = await _draft_revision(connection, version.site_id)
                    if stored != draft_revision:
                        raise ConflictError(DRAFT_CHANGED)
                await connection.execute(insert(versions_table).values(values))
                await connection.execute(
                    delete(drafts_table).where(drafts_table.c.site_id == version.site_id)
                )
        except IntegrityError as error:
            raise ConflictError(
                f"site {version.site_id} already has knowledge version {version.version}"
            ) from error
