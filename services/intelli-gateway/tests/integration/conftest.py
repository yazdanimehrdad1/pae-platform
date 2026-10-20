"""Integration fixtures. The Postgres ones only work through `make test-integration`, which
starts a throwaway database and sets INTELLI_GATEWAY_TEST_DATABASE_URL and
INTEGRATION_DB_RESET_ALLOWED=1; without both, tests using them are skipped (they drop the
schema). The real-Claude test (`make test-llm`) needs neither."""

import os
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest

from intelli_gateway.services.postgres.database import (
    create_database_engine,
    migrate,
    wait_for_database,
)
from intelli_gateway.services.postgres.forecast_repository import PostgresForecastRepository

DATABASE_URL = os.environ.get("INTELLI_GATEWAY_TEST_DATABASE_URL", "")
RESET_ALLOWED = os.environ.get("INTEGRATION_DB_RESET_ALLOWED") == "1"


@pytest.fixture
def database_url() -> str:
    if not (DATABASE_URL and RESET_ALLOWED):
        pytest.skip(
            "needs the throwaway database: run `make -C services/intelli-gateway test-integration`"
        )
    return DATABASE_URL


async def reset_database(url: str) -> list[str]:
    """Drop everything and apply every migration from zero; returns the versions applied."""
    engine = create_database_engine(url)
    try:
        await wait_for_database(engine)
        async with engine.begin() as connection:
            await connection.exec_driver_sql("DROP SCHEMA public CASCADE")
            await connection.exec_driver_sql("CREATE SCHEMA public")
        return await migrate(engine)
    finally:
        await engine.dispose()


@pytest.fixture
async def repository(database_url: str) -> AsyncIterator[PostgresForecastRepository]:
    await reset_database(database_url)
    repository = PostgresForecastRepository(create_database_engine(database_url))
    try:
        yield repository
    finally:
        await repository.aclose()


@pytest.fixture
def reset(database_url: str) -> Callable[[], Awaitable[list[str]]]:
    """Reset the throwaway database to a fresh install; returns the migrations applied."""
    return lambda: reset_database(database_url)
