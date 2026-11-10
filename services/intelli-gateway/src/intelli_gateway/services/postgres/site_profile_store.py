"""PostgresSiteProfileStore: approved site profile versions and the latest backend-ot catalogs in
this service's Postgres (SQLAlchemy 2 Core over asyncpg). Tables: migration 005_site_profiles."""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    func,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from intelli_gateway.schemas.site_profile import CatalogSnapshot, ProfileVersion
from intelli_gateway.utils.exceptions import ConflictError

metadata = MetaData()
versions_table = Table(
    "site_profile_versions",
    metadata,
    Column("site_id", BigInteger(), primary_key=True),
    Column("version", Integer(), primary_key=True),
    Column("catalog", JSONB(), nullable=False),
    Column("approved_at", DateTime(timezone=True), nullable=False),
    Column("approved_by", Text(), nullable=False),
    Column("change_ids", JSONB(), nullable=False),
)
snapshots_table = Table(
    "site_catalog_snapshots",
    metadata,
    Column("site_id", BigInteger(), primary_key=True),
    Column("catalog", JSONB(), nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
)


def _profile(row: RowMapping) -> ProfileVersion:
    return ProfileVersion.model_validate(dict(row))


def _snapshot(row: RowMapping) -> CatalogSnapshot:
    return CatalogSnapshot.model_validate(dict(row))


class PostgresSiteProfileStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get_profile(self, site_id: int) -> ProfileVersion | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(versions_table)
                .where(versions_table.c.site_id == site_id)
                .order_by(versions_table.c.version.desc())
                .limit(1)
            )
            row = result.mappings().one_or_none()
        return _profile(row) if row is not None else None

    async def list_profiles(self) -> list[ProfileVersion]:
        latest = (
            select(versions_table.c.site_id, func.max(versions_table.c.version).label("version"))
            .group_by(versions_table.c.site_id)
            .subquery()
        )
        query = (
            select(versions_table)
            .join(
                latest,
                (versions_table.c.site_id == latest.c.site_id)
                & (versions_table.c.version == latest.c.version),
            )
            .order_by(versions_table.c.site_id)
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(query)
            return [_profile(row) for row in result.mappings()]

    async def list_versions(self, site_id: int) -> list[ProfileVersion]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(versions_table)
                .where(versions_table.c.site_id == site_id)
                .order_by(versions_table.c.version.desc())
            )
            return [_profile(row) for row in result.mappings()]

    async def add_version(self, profile: ProfileVersion) -> None:
        values = {
            "site_id": profile.site_id,
            "version": profile.version,
            "catalog": profile.catalog.model_dump(mode="json"),
            "approved_at": profile.approved_at,
            "approved_by": profile.approved_by,
            "change_ids": list(profile.change_ids),
        }
        try:
            async with self._engine.begin() as connection:
                await connection.execute(insert(versions_table).values(values))
        except IntegrityError as error:
            raise ConflictError(
                f"site {profile.site_id} already has profile version {profile.version}"
            ) from error

    async def get_snapshot(self, site_id: int) -> CatalogSnapshot | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(snapshots_table).where(snapshots_table.c.site_id == site_id)
            )
            row = result.mappings().one_or_none()
        return _snapshot(row) if row is not None else None

    async def list_snapshots(self) -> list[CatalogSnapshot]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(snapshots_table).order_by(snapshots_table.c.site_id)
            )
            return [_snapshot(row) for row in result.mappings()]

    async def save_snapshot(self, snapshot: CatalogSnapshot) -> None:
        values = {
            "site_id": snapshot.site_id,
            "catalog": snapshot.catalog.model_dump(mode="json"),
            "fetched_at": snapshot.fetched_at,
        }
        statement = pg_insert(snapshots_table).values(values)
        async with self._engine.begin() as connection:
            await connection.execute(
                statement.on_conflict_do_update(
                    index_elements=[snapshots_table.c.site_id],
                    set_={
                        "catalog": statement.excluded.catalog,
                        "fetched_at": statement.excluded.fetched_at,
                    },
                )
            )
