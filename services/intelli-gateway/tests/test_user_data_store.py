"""The in-memory UserDataStore passes the shared store contract (the Postgres one runs the same
checks in tests/integration/test_postgres_user_data_store.py).

Invariant guarded: preferences hold any JSON and overwrite by key; trends keep the user's order
(appended last, gaps closed on delete, reorderable); notes list newest first; and one user can
never list, read, change or delete another user's preferences, trends or notes.
"""

from collections.abc import Awaitable, Callable

import pytest
from user_data_store_contract import CHECKS

from intelli_gateway.fake_data.user_data_store import InMemoryUserDataStore
from intelli_gateway.interfaces.user_data_store import UserDataStore


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_in_memory_user_data_store(
    check: Callable[[UserDataStore], Awaitable[None]],
) -> None:
    await check(InMemoryUserDataStore())
