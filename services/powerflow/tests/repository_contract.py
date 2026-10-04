"""Behaviour every ConfigRepository must have. Run against InMemoryConfigRepository in the unit
tests (test_storage.py) and against Postgres in tests/integration/. Each check starts from an
empty repository."""

import pytest
from conftest import default_site, make_site_config

from powerflow.errors import NotFoundError
from powerflow.storage import ConfigRepository, SiteCategory, StoredSite

CUSTOM = SiteCategory.CUSTOM


async def check_sites(repository: ConfigRepository) -> None:
    assert await repository.list_sites() == []
    config = make_site_config(n_bess=2)
    await repository.put_site("alpha", config)
    await repository.put_site("beta", default_site("2bess_1pv"))
    assert await repository.list_sites() == [
        StoredSite(name="alpha", category=CUSTOM),
        StoredSite(name="beta", category=CUSTOM),
    ]
    assert await repository.get_site("alpha") == config
    replacement = make_site_config(n_bess=1)
    await repository.put_site("alpha", replacement)  # upsert
    assert await repository.get_site("alpha") == replacement
    assert (await repository.list_sites())[0].category is CUSTOM  # an upsert keeps the category
    await repository.delete_site("alpha")
    assert await repository.list_sites() == [StoredSite(name="beta", category=CUSTOM)]
    with pytest.raises(NotFoundError):
        await repository.get_site("alpha")
    with pytest.raises(NotFoundError):
        await repository.delete_site("alpha")


async def check_active_site(repository: ConfigRepository) -> None:
    assert await repository.get_active_site() is None
    with pytest.raises(NotFoundError):
        await repository.set_active_site("missing")
    await repository.put_site("alpha", make_site_config())
    await repository.set_active_site("alpha")
    assert await repository.get_active_site() == "alpha"
    await repository.delete_site("alpha")
    assert await repository.get_active_site() is None


CONTRACT_CHECKS = [check_sites, check_active_site]
