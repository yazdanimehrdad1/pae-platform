"""Integration tests against a real Postgres. Only run through `make test-integration`, which
starts a throwaway database and sets POWERFLOW_TEST_DATABASE_URL and
INTEGRATION_DB_RESET_ALLOWED=1. Without both, every test here is skipped: they truncate tables."""

import asyncio
import os
from collections.abc import Callable, Coroutine

import pytest

from powerflow.storage.postgres import (
    PostgresConfigRepository,
    create_database_engine,
    migrate,
    wait_for_database,
)

DATABASE_URL = os.environ.get("POWERFLOW_TEST_DATABASE_URL", "")
RESET_ALLOWED = os.environ.get("INTEGRATION_DB_RESET_ALLOWED") == "1"


@pytest.fixture(autouse=True)
def _require_throwaway_database() -> None:
    if not (DATABASE_URL and RESET_ALLOWED):
        pytest.skip(
            "needs the throwaway database: run `make -C services/powerflow test-integration`"
        )


async def reset_database() -> None:
    """Migrate, then empty every table."""
    engine = create_database_engine(DATABASE_URL)
    try:
        await wait_for_database(engine)
        await migrate(engine)
        async with engine.begin() as connection:
            await connection.exec_driver_sql("TRUNCATE sites, modbus_maps, app_state CASCADE")
    finally:
        await engine.dispose()


def run_with_repository(
    check: Callable[[PostgresConfigRepository], Coroutine[object, object, None]],
) -> None:
    async def body() -> None:
        await reset_database()
        repository = PostgresConfigRepository(create_database_engine(DATABASE_URL))
        try:
            await check(repository)
        finally:
            await repository.close()

    asyncio.run(body())
