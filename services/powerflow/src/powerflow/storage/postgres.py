"""PostgresConfigRepository: sites and the active site in Postgres (SQLAlchemy 2 Core, asyncpg).
Configs are JSONB, validated by the Pydantic model on the way in and out, and stored in full
(every field explicit), so a later change to a code default never changes a stored site.

Migrations are the SQL files in storage/migrations/, applied in name order at startup and
recorded in schema_migrations (guarded by an advisory lock, so concurrent starts are safe).
0003_default_sites.sql inserts the default sites: the database is the only store for sites.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import TypeVar

from sqlalchemy import (
    Column,
    DateTime,
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

from powerflow.conditions.scenario import EventScenario
from powerflow.errors import NotFoundError, SiteConfigError
from powerflow.site_config import SiteConfig
from powerflow.storage.repository import ConfigRepository, SiteCategory, StoredSite

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
MIGRATION_LOCK_KEY = 0x70F0_F10E  # any constant shared by every powerflow instance
ACTIVE_SITE_KEY = "active_site"

metadata = MetaData()
sites_table = Table(
    "sites",
    metadata,
    Column("name", Text, primary_key=True),
    Column("config", JSONB, nullable=False),
    Column("category", Text, nullable=False, server_default=SiteCategory.CUSTOM.value),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
event_scenarios_table = Table(
    "event_scenarios",
    metadata,
    Column("site", Text, primary_key=True),
    Column("name", Text, primary_key=True),
    Column("scenario", JSONB, nullable=False),
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


DOLLAR_QUOTE = re.compile(r"\$[A-Za-z_]*\$")


def _statements(sql: str) -> list[str]:
    """Split a migration into statements on `;`, except inside dollar-quoted text ($tag$...$tag$,
    which holds the default sites' JSON). Whole-line `--` comments are dropped."""
    body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    statements: list[str] = []
    start = index = 0
    while index < len(body):
        quote = DOLLAR_QUOTE.match(body, index)
        if quote:
            closing = body.find(quote.group(), quote.end())
            index = len(body) if closing == -1 else closing + len(quote.group())
            continue
        if body[index] == ";":
            statements.append(body[start:index])
            start = index + 1
        index += 1
    statements.append(body[start:])
    return [statement.strip() for statement in statements if statement.strip()]


class PostgresConfigRepository(ConfigRepository):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def list_sites(self) -> list[StoredSite]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(sites_table.c.name, sites_table.c.category).order_by("name")
            )
            return [
                StoredSite(name=row.name, category=SiteCategory(row.category)) for row in result
            ]

    async def get_site(self, name: str) -> SiteConfig:
        async with self._engine.connect() as connection:
            config = await connection.scalar(
                select(sites_table.c.config).where(sites_table.c.name == name)
            )
        if config is None:
            raise NotFoundError(f"no site {name!r}")
        return _validate(SiteConfig, config, f"site {name!r}")

    async def put_site(self, name: str, config: SiteConfig) -> None:
        document = config.model_dump(mode="json")
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

    async def list_event_scenarios(self, site: str) -> list[str]:
        async with self._engine.connect() as connection:
            await _require_site(connection, site)
            result = await connection.execute(
                select(event_scenarios_table.c.name)
                .where(event_scenarios_table.c.site == site)
                .order_by("name")
            )
            return [row.name for row in result]

    async def get_event_scenario(self, site: str, name: str) -> EventScenario:
        async with self._engine.connect() as connection:
            document = await connection.scalar(
                select(event_scenarios_table.c.scenario).where(
                    event_scenarios_table.c.site == site, event_scenarios_table.c.name == name
                )
            )
        if document is None:
            raise NotFoundError(f"no event scenario {name!r} for site {site!r}")
        return _validate(EventScenario, document, f"event scenario {site}/{name}")

    async def put_event_scenario(self, site: str, name: str, scenario: EventScenario) -> None:
        document = scenario.model_dump(mode="json")
        statement = insert(event_scenarios_table).values(site=site, name=name, scenario=document)
        statement = statement.on_conflict_do_update(
            index_elements=[event_scenarios_table.c.site, event_scenarios_table.c.name],
            set_={"scenario": statement.excluded.scenario, "updated_at": func.now()},
        )
        async with self._engine.begin() as connection:
            await _require_site(connection, site)
            await connection.execute(statement)

    async def delete_event_scenario(self, site: str, name: str) -> None:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                delete(event_scenarios_table)
                .where(event_scenarios_table.c.site == site, event_scenarios_table.c.name == name)
                .returning(event_scenarios_table.c.name)
            )
            if result.first() is None:
                raise NotFoundError(f"no event scenario {name!r} for site {site!r}")

    async def close(self) -> None:
        await self._engine.dispose()


async def _require_site(connection: AsyncConnection, name: str) -> None:
    exists = await connection.scalar(select(sites_table.c.name).where(sites_table.c.name == name))
    if exists is None:
        raise NotFoundError(f"no site {name!r}")


StoredModel = TypeVar("StoredModel", SiteConfig, EventScenario)


def _validate(model: type[StoredModel], document: object, label: str) -> StoredModel:
    try:
        return model.model_validate(document)
    except ValueError as error:
        raise SiteConfigError(f"stored {label} is invalid:\n{error}") from error
