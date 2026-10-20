"""PostgresForecastRepository against a real (throwaway) Postgres: the shared repository
contract, plus the migrations.

Invariant guarded: every migration applies from zero and a second run applies nothing; the
Postgres repository passes the same contract as the in-memory one; deleting a run removes its
intervals (ON DELETE CASCADE).
"""

from collections.abc import Awaitable, Callable

import pytest
from forecast_repository_contract import CHECKS, ISSUED, forecast
from sqlalchemy import text

from intelli_gateway.interfaces.forecast_repository import ForecastRepository
from intelli_gateway.services.postgres.database import (
    MIGRATIONS_DIR,
    create_database_engine,
    migrate,
)
from intelli_gateway.services.postgres.forecast_repository import PostgresForecastRepository


async def test_migrations_apply_from_zero_once(
    database_url: str, reset: Callable[[], Awaitable[list[str]]]
) -> None:
    applied = await reset()
    assert applied == [path.stem for path in sorted(MIGRATIONS_DIR.glob("*.sql"))]
    engine = create_database_engine(database_url)
    try:
        assert await migrate(engine) == []
    finally:
        await engine.dispose()


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_postgres_repository(
    repository: PostgresForecastRepository,
    check: Callable[[ForecastRepository], Awaitable[None]],
) -> None:
    await check(repository)


async def test_retention_cascades_to_intervals(
    repository: PostgresForecastRepository, database_url: str
) -> None:
    await repository.save(forecast(issued_at=ISSUED))
    await repository.delete_issued_before(ISSUED.replace(year=2027))
    engine = create_database_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT count(*) FROM forecast_intervals"))
            count = result.scalar_one()
    finally:
        await engine.dispose()
    assert count == 0
