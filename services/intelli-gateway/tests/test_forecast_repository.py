"""The in-memory ForecastRepository passes the shared repository contract (the Postgres one runs
the same checks in tests/integration/test_postgres_forecast_repository.py).

Invariant guarded: a saved forecast reads back equal (weather, per-array rows, PV-power-only
runs, the fallback flag); history is kept and read by issue time (strictly before); the fetch
log answers last attempt / last success / last failure; retention drops old runs and log rows.
"""

from collections.abc import Awaitable, Callable

import pytest
from forecast_repository_contract import CHECKS

from intelli_gateway.fake_data.forecast import InMemoryForecastRepository
from intelli_gateway.interfaces.forecast_repository import ForecastRepository


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_in_memory_repository(
    check: Callable[[ForecastRepository], Awaitable[None]],
) -> None:
    await check(InMemoryForecastRepository())
