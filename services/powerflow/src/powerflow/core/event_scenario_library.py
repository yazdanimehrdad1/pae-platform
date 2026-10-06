"""EventScenarioLibrary: the stored event scenarios (per site) and starting one on the engine.

A scenario is validated against its site's stored config when it's saved, again when listed
(a later site edit can make it stale: `valid` / `problems`), and against the running config when
it's started.
"""

from powerflow.conditions.scenario import (
    ConditionsReport,
    EventScenario,
    EventScenarioSummary,
    validate_scenario,
)
from powerflow.core.engine import Engine
from powerflow.core.site_library import SiteLibrary
from powerflow.errors import ConditionError
from powerflow.storage import ConfigRepository
from powerflow.storage.names import check_event_scenario_name, check_site_name


class EventScenarioLibrary:
    def __init__(
        self, repository: ConfigRepository, engine: Engine, site_library: SiteLibrary
    ) -> None:
        self._repository = repository
        self._engine = engine
        self._site_library = site_library

    async def list(self, site: str) -> list[EventScenarioSummary]:
        config = await self._repository.get_site(check_site_name(site))
        summaries: list[EventScenarioSummary] = []
        for name in await self._repository.list_event_scenarios(site):
            scenario = await self._repository.get_event_scenario(site, name)
            problems = validate_scenario(scenario, config)
            summaries.append(
                EventScenarioSummary(
                    name=name,
                    description=scenario.description,
                    event_count=len(scenario.events),
                    valid=not problems,
                    problems=problems,
                )
            )
        return summaries

    async def get(self, site: str, name: str) -> EventScenario:
        return await self._repository.get_event_scenario(
            check_site_name(site), check_event_scenario_name(name)
        )

    async def save(self, site: str, name: str, scenario: EventScenario) -> EventScenario:
        """Validate against the site's stored config, then store."""
        config = await self._repository.get_site(check_site_name(site))
        check_event_scenario_name(name)
        problems = validate_scenario(scenario, config)
        if problems:
            raise ConditionError("; ".join(problems))
        await self._repository.put_event_scenario(site, name, scenario)
        return scenario

    async def delete(self, site: str, name: str) -> None:
        await self._repository.delete_event_scenario(
            check_site_name(site), check_event_scenario_name(name)
        )

    async def start(self, name: str) -> ConditionsReport:
        """Play one of the active site's scenarios from the current step."""
        site = self._site_library.active_site
        scenario = await self._repository.get_event_scenario(site, check_event_scenario_name(name))
        return await self._engine.start_scenario(name, scenario)
