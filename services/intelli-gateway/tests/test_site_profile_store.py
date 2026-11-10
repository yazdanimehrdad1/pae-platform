"""The in-memory SiteProfileStore passes the shared store contract (the Postgres one runs the same
checks in tests/integration/test_postgres_site_profile_store.py).

Invariant guarded: approved versions read back exactly and the highest is the current one; a
version number is stored once; each site keeps only its latest fetched catalog.
"""

from collections.abc import Awaitable, Callable

import pytest
from doubles.site_profile_store import InMemorySiteProfileStore
from site_profile_store_contract import CHECKS

from intelli_gateway.interfaces.site_profile_store import SiteProfileStore


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_in_memory_site_profile_store(
    check: Callable[[SiteProfileStore], Awaitable[None]],
) -> None:
    await check(InMemorySiteProfileStore())
