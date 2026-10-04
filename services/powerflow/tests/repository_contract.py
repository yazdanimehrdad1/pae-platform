"""Behaviour every ConfigRepository must have. Run against InMemoryConfigRepository in the unit
tests (test_storage.py) and against Postgres in tests/integration/. Each check starts from an
empty repository."""

import pytest
from conftest import default_site, make_site_config

from powerflow.conditions import BreakerChange
from powerflow.conditions.scenario import EventScenario, ScenarioEvent, StepTrigger
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


def scenario_with(breaker: str) -> EventScenario:
    return EventScenario(
        events=[
            ScenarioEvent(
                at=StepTrigger(step=1), change=BreakerChange(breaker=breaker, closed=False)
            )
        ]
    )


async def check_event_scenarios(repository: ConfigRepository) -> None:
    with pytest.raises(NotFoundError):
        await repository.list_event_scenarios("alpha")
    with pytest.raises(NotFoundError):
        await repository.put_event_scenario("alpha", "trip", scenario_with("bess1"))
    await repository.put_site("alpha", make_site_config())
    await repository.put_site("beta", make_site_config())
    assert await repository.list_event_scenarios("alpha") == []
    await repository.put_event_scenario("alpha", "trip", scenario_with("bess1"))
    await repository.put_event_scenario("alpha", "blackout", scenario_with("poi"))
    await repository.put_event_scenario("beta", "trip", scenario_with("pv1"))
    assert await repository.list_event_scenarios("alpha") == ["blackout", "trip"]
    assert await repository.get_event_scenario("beta", "trip") == scenario_with("pv1")
    await repository.put_event_scenario("alpha", "trip", scenario_with("load1"))  # upsert
    assert await repository.get_event_scenario("alpha", "trip") == scenario_with("load1")
    await repository.delete_event_scenario("alpha", "blackout")
    with pytest.raises(NotFoundError):
        await repository.get_event_scenario("alpha", "blackout")
    with pytest.raises(NotFoundError):
        await repository.delete_event_scenario("alpha", "blackout")
    await repository.delete_site("alpha")  # its scenarios go with it
    with pytest.raises(NotFoundError):
        await repository.get_event_scenario("alpha", "trip")
    assert await repository.list_event_scenarios("beta") == ["trip"]


CONTRACT_CHECKS = [check_sites, check_active_site, check_event_scenarios]
