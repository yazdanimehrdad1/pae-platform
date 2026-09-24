"""
Shared fixtures for integration tests.

Integration tests drive the real FastAPI app (in-process, via httpx's ASGI transport)
against a real Postgres and Redis. Every test starts from empty tables and an empty
Redis DB, so tests are independent and can run in any order.

Safety: the reset fixture TRUNCATEs every service table and FLUSHDBs Redis. It only does
so when INTEGRATION_DB_RESET_ALLOWED=1, which is set by compose.test.yaml (the
throwaway test stack) and CI. Anywhere else, integration tests are skipped, so a bare
`pytest tests/` pointed at a dev database can never wipe it.
"""

import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from app import create_app
from cache.connection import close_redis_client, get_redis_client
from config import settings
from db.connection import close_all_db_connections

# Child tables first is not required with CASCADE, but listing all of them makes the
# intent explicit. RESTART IDENTITY resets sites_id_seq back to its START (1001).
SERVICE_TABLES = ("device_points_readings", "device_points", "devices", "sites")

RESET_ALLOWED = os.environ.get("INTEGRATION_DB_RESET_ALLOWED") == "1"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if RESET_ALLOWED:
        return
    skip = pytest.mark.skip(
        reason="integration tests need the throwaway test stack: run `make test-integration`"
    )
    for item in items:
        if "tests/integration/" in item.nodeid.replace("\\", "/"):
            item.add_marker(skip)


async def _connect_db() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )


@pytest.fixture(autouse=True)
async def reset_state() -> AsyncIterator[None]:
    """Empty every table and Redis before each test; drop pooled connections after."""
    connection = await _connect_db()
    try:
        await connection.execute(f"TRUNCATE {', '.join(SERVICE_TABLES)} RESTART IDENTITY CASCADE")
    finally:
        await connection.close()
    redis_client = await get_redis_client()
    await redis_client.flushdb()

    yield

    # The app keeps module-level asyncpg/SQLAlchemy/Redis pools. Each test runs in its own
    # event loop, so pools created in one test must not leak into the next.
    await close_all_db_connections()
    await close_redis_client()


@pytest.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    """A raw DB connection for arranging state the API can't create (e.g. readings)."""
    connection = await _connect_db()
    try:
        yield connection
    finally:
        await connection.close()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTP client bound to a fresh app. Lifespan is not run, so the scheduler never starts."""
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
