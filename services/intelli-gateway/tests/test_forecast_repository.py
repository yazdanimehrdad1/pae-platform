"""The in-memory ForecastRepository passes the shared repository contract (the Postgres one runs
the same checks in tests/integration/test_postgres_forecast_repository.py).

Invariant guarded: a saved forecast reads back equal (weather, per-array rows, PV-power-only
runs, the fallback flag); each interval is read from the newest run issued at or before its
start; saving prunes the rows a newer run supersedes (one forecast kept per interval); the fetch
log answers last attempt / last success / last failure; retention drops old runs and log rows.
"""

from collections.abc import Awaitable, Callable

import pytest
from forecast_repository_contract import CHECKS, ISSUED, STEP, forecast

from intelli_gateway.fake_data.forecast import InMemoryForecastRepository
from intelli_gateway.interfaces.forecast_repository import ForecastRepository


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_in_memory_repository(
    check: Callable[[ForecastRepository], Awaitable[None]],
) -> None:
    await check(InMemoryForecastRepository())


async def test_pruning_keeps_one_forecast_per_interval() -> None:
    repository = InMemoryForecastRepository()
    for index in range(10):
        await repository.save(forecast(issued_at=ISSUED + index * STEP, intervals=12))
    # 9 superseded runs keep only their first interval; the newest keeps all 12.
    assert [len(run.intervals) for run in repository.forecasts] == [1] * 9 + [12]
