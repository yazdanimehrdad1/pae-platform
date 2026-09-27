"""PostgresConfigRepository: sites, Modbus maps and the active site in Postgres (SQLAlchemy 2
Core, asyncpg). Configs are JSONB, validated by the Pydantic models on the way in and out.

Migrations are the SQL files in storage/migrations/, applied in name order at startup and
recorded in schema_migrations (guarded by an advisory lock, so concurrent starts are safe).
"""

import asyncio
import logging
from pathlib import Path
from typing import TypeVar

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    Table,
    Text,
    delete,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from powerflow.errors import NotFoundError, SiteConfigError
from powerflow.points.modbus_map import ModbusMap
from powerflow.site_config import SiteConfig
from powerflow.storage.repository import ConfigRepository

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
MIGRATION_LOCK_KEY = 0x70F0_F10E  # any constant shared by every powerflow instance
ACTIVE_SITE_KEY = "active_site"
ModelType = TypeVar("ModelType", SiteConfig, ModbusMap)

metadata = MetaData()
sites_table = Table(
    "sites",
    metadata,
    Column("name", Text, primary_key=True),
    Column("config", JSONB, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
maps_table = Table(
    "modbus_maps",
    metadata,
    Column("site", Text, ForeignKey("sites.name", ondelete="CASCADE"), primary_key=True),
    Column("asset", Text, primary_key=True),
    Column("map", JSONB, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
state_table = Table(
    "app_state",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", JSONB, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


def create_database_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


async def wait_for_database(engine: AsyncEngine, timeout_s: float = 30.0) -> None:
    """Retry until the database answers (it may still be starting next to us)."""
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return
        except (OSError, OperationalError, DBAPIError) as error:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            logger.info("waiting for the database: %s", error.__class__.__name__)
            await asyncio.sleep(1.0)


async def migrate(engine: AsyncEngine) -> list[str]:
    """Apply pending migrations; returns the versions applied now."""
    applied_now: list[str] = []
    async with engine.begin() as connection:
        await connection.exec_driver_sql(f"SELECT pg_advisory_xact_lock({MIGRATION_LOCK_KEY})")
        await connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        result = await connection.exec_driver_sql("SELECT version FROM schema_migrations")
        applied = {row[0] for row in result}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in applied:
                continue
            for statement in _statements(path.read_text(encoding="utf-8")):
                await connection.exec_driver_sql(statement)
            await connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": path.stem},
            )
            applied_now.append(path.stem)
    if applied_now:
        logger.info("applied migrations %s", applied_now)
    return applied_now


def _statements(sql: str) -> list[str]:
    """Split a migration into statements (no semicolons inside statements in our SQL)."""
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]


class PostgresConfigRepository(ConfigRepository):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def is_empty(self) -> bool:
        async with self._engine.connect() as connection:
            count = await connection.scalar(select(func.count()).select_from(sites_table))
        return not count

    async def list_sites(self) -> list[str]:
        async with self._engine.connect() as connection:
            result = await connection.execute(select(sites_table.c.name).order_by("name"))
            return [row.name for row in result]

    async def get_site(self, name: str) -> SiteConfig:
        async with self._engine.connect() as connection:
            config = await connection.scalar(
                select(sites_table.c.config).where(sites_table.c.name == name)
            )
        if config is None:
            raise NotFoundError(f"no site {name!r}")
        return _validate(SiteConfig, config, f"site {name!r}")

    async def put_site(self, name: str, config: SiteConfig) -> None:
        document = config.model_dump(mode="json", exclude_unset=True)
        statement = insert(sites_table).values(name=name, config=document)
        statement = statement.on_conflict_do_update(
            index_elements=[sites_table.c.name],
            set_={"config": statement.excluded.config, "updated_at": func.now()},
        )
        async with self._engine.begin() as connection:
            await connection.execute(statement)

    async def delete_site(self, name: str) -> None:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                delete(sites_table).where(sites_table.c.name == name).returning(sites_table.c.name)
            )
            if result.first() is None:
                raise NotFoundError(f"no site {name!r}")
            await connection.execute(
                delete(state_table).where(
                    state_table.c.key == ACTIVE_SITE_KEY,
                    state_table.c.value["site"].astext == name,
                )
            )

    async def get_active_site(self) -> str | None:
        async with self._engine.connect() as connection:
            value = await connection.scalar(
                select(state_table.c.value).where(state_table.c.key == ACTIVE_SITE_KEY)
            )
        return value["site"] if isinstance(value, dict) else None

    async def set_active_site(self, name: str) -> None:
        async with self._engine.begin() as connection:
            await _require_site(connection, name)
            statement = insert(state_table).values(key=ACTIVE_SITE_KEY, value={"site": name})
            statement = statement.on_conflict_do_update(
                index_elements=[state_table.c.key],
                set_={"value": statement.excluded.value, "updated_at": func.now()},
            )
            await connection.execute(statement)

    async def list_maps(self, site: str) -> list[str]:
        async with self._engine.connect() as connection:
            await _require_site(connection, site)
            result = await connection.execute(
                select(maps_table.c.asset).where(maps_table.c.site == site).order_by("asset")
            )
            return [row.asset for row in result]

    async def get_map(self, site: str, asset: str) -> ModbusMap:
        async with self._engine.connect() as connection:
            await _require_site(connection, site)
            document = await connection.scalar(
                select(maps_table.c.map).where(
                    maps_table.c.site == site, maps_table.c.asset == asset
                )
            )
        if document is None:
            raise NotFoundError(f"no Modbus map {asset!r} in site {site!r}")
        return _validate(ModbusMap, document, f"Modbus map {site}/{asset}")

    async def put_map(self, site: str, asset: str, modbus_map: ModbusMap) -> None:
        document = modbus_map.model_dump(mode="json", exclude_unset=True)
        statement = insert(maps_table).values(site=site, asset=asset, map=document)
        statement = statement.on_conflict_do_update(
            index_elements=[maps_table.c.site, maps_table.c.asset],
            set_={"map": statement.excluded.map, "updated_at": func.now()},
        )
        async with self._engine.begin() as connection:
            await _require_site(connection, site)
            await connection.execute(statement)

    async def delete_map(self, site: str, asset: str) -> None:
        async with self._engine.begin() as connection:
            await _require_site(connection, site)
            result = await connection.execute(
                delete(maps_table)
                .where(maps_table.c.site == site, maps_table.c.asset == asset)
                .returning(maps_table.c.asset)
            )
            if result.first() is None:
                raise NotFoundError(f"no Modbus map {asset!r} in site {site!r}")

    async def close(self) -> None:
        await self._engine.dispose()


async def _require_site(connection: AsyncConnection, name: str) -> None:
    exists = await connection.scalar(select(sites_table.c.name).where(sites_table.c.name == name))
    if exists is None:
        raise NotFoundError(f"no site {name!r}")


def _validate(model: type[ModelType], document: object, label: str) -> ModelType:
    try:
        return model.model_validate(document)
    except ValueError as error:
        raise SiteConfigError(f"stored {label} is invalid:\n{error}") from error
