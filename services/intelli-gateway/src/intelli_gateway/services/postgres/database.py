"""The async engine and the migration runner.

Migrations are the numbered SQL files in migrations/, applied in name order at startup and
recorded in schema_migrations, under an advisory lock so concurrent starts are safe. The version
is the file stem: never rename or edit an applied file; add a new one.
"""

import asyncio
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
MIGRATION_LOCK_KEY = 0x1A7E_6A7E  # any constant shared by every intelli-gateway instance


def create_database_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


async def wait_for_database(engine: AsyncEngine, timeout_s: float = 30.0) -> None:
    """Retry until the database answers (it may still be starting next to us)."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while True:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return
        except (OSError, OperationalError, DBAPIError) as error:
            if loop.time() >= deadline:
                raise
            logger.info("waiting_for_database", extra={"fields": {"error": type(error).__name__}})
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
        applied = {str(row[0]) for row in result}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in applied:
                continue
            for statement in split_statements(path.read_text(encoding="utf-8")):
                await connection.exec_driver_sql(statement)
            await connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": path.stem},
            )
            applied_now.append(path.stem)
    if applied_now:
        logger.info("migrations_applied", extra={"fields": {"versions": applied_now}})
    return applied_now


def split_statements(sql: str) -> list[str]:
    """Split a migration on `;` outside single-quoted strings. Whole-line `--` comments are
    dropped. (No dollar-quoted bodies are supported; add that before writing one.)"""
    body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    for char in body:
        if char == "'":
            in_string = not in_string  # an escaped '' toggles twice
        if char == ";" and not in_string:
            statements.append("".join(current))
            current = []
            continue
        current.append(char)
    statements.append("".join(current))
    return [statement.strip() for statement in statements if statement.strip()]
