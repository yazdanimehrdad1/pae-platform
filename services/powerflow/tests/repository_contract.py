"""Behaviour every ConfigRepository must have. Run against InMemoryConfigRepository in the unit
tests (test_storage.py) and against Postgres in tests/integration/."""

import pytest
from conftest import default_site, default_site_maps, make_site_config

from powerflow.errors import NotFoundError
from powerflow.storage import ConfigRepository


async def check_sites(repository: ConfigRepository) -> None:
    assert await repository.is_empty()
    config = make_site_config(n_bess=2)
    await repository.put_site("alpha", config)
    await repository.put_site("beta", default_site("reference_2bess_1pv"))
    assert not await repository.is_empty()
    assert await repository.list_sites() == ["alpha", "beta"]
    assert await repository.get_site("alpha") == config
    replacement = make_site_config(n_bess=1)
    await repository.put_site("alpha", replacement)  # upsert
    assert await repository.get_site("alpha") == replacement
    await repository.delete_site("alpha")
    assert await repository.list_sites() == ["beta"]
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


async def check_maps(repository: ConfigRepository) -> None:
    maps = default_site_maps("reference_2bess_1pv")
    with pytest.raises(NotFoundError):
        await repository.put_map("missing", "bess.bess1", maps["bess.bess1"])
    await repository.put_site("site", default_site("reference_2bess_1pv"))
    for asset, modbus_map in maps.items():
        await repository.put_map("site", asset, modbus_map)
    assert await repository.list_maps("site") == sorted(maps)
    assert await repository.get_map("site", "pv.pv1") == maps["pv.pv1"]
    edited = maps["pv.pv1"].model_copy(update={"unit_id": 42})
    await repository.put_map("site", "pv.pv1", edited)  # upsert
    assert (await repository.get_map("site", "pv.pv1")).unit_id == 42
    await repository.delete_map("site", "pv.pv1")
    with pytest.raises(NotFoundError):
        await repository.get_map("site", "pv.pv1")
    with pytest.raises(NotFoundError):
        await repository.delete_map("site", "pv.pv1")
    with pytest.raises(NotFoundError):
        await repository.list_maps("missing")
    await repository.delete_site("site")  # cascades to its maps
    await repository.put_site("site", default_site("reference_2bess_1pv"))
    assert await repository.list_maps("site") == []


CONTRACT_CHECKS = [check_sites, check_active_site, check_maps]
