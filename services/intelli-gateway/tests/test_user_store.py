"""The in-memory UserStore passes the shared store contract (the Postgres one runs the same checks
in tests/integration/test_postgres_user_store.py).

Invariant guarded: users read back as created, emails are unique, sessions are stored,
slid and deleted by token hash, and disabling a user or changing their password ends all of
that user's sessions and nobody else's.
"""

from collections.abc import Awaitable, Callable

import pytest
from doubles.user_store import InMemoryUserStore
from user_store_contract import CHECKS

from intelli_gateway.interfaces.user_store import UserStore


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_in_memory_user_store(check: Callable[[UserStore], Awaitable[None]]) -> None:
    await check(InMemoryUserStore())
