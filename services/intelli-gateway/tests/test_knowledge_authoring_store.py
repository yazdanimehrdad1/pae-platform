"""The in-memory KnowledgeAuthoringStore passes the shared store contract (the Postgres one runs
the same checks in tests/integration/test_postgres_knowledge_authoring_store.py).

Invariant guarded: a draft is saved only at the next revision (an edit made against an older one
is refused); publishing stores the version and ends the draft in one step, and refuses a draft
edited since it was reviewed; version numbers are taken once and listed newest first.
"""

from collections.abc import Awaitable, Callable

import pytest
from doubles.knowledge_authoring_store import InMemoryKnowledgeAuthoringStore
from knowledge_authoring_store_contract import CHECKS

from intelli_gateway.interfaces.knowledge_authoring_store import KnowledgeAuthoringStore


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
async def test_in_memory_knowledge_authoring_store(
    check: Callable[[KnowledgeAuthoringStore], Awaitable[None]],
) -> None:
    await check(InMemoryKnowledgeAuthoringStore())
