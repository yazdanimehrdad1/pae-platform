"""EventScenarioLibrary: the stored event scenarios (per site) and starting one on the engine.

A scenario is validated against its site's stored config when it's saved, again when listed
(a later site edit can make it stale: `valid` / `problems`), and against the running config when
it's started. Its expected points are checked against the site's point-standard layout by
`check_points` (injected: the point standard sits above core).

The built-in library (conditions/builtin_scenarios.py) is synced to every default site at
startup, as category `default`: added or updated from the code, and removed when the library
drops one. Built-ins are read-only (no save, no delete); duplicate one to customize it.
"""

import logging
from collections.abc import Callable

from powerflow.conditions.builtin_scenarios import BUILTIN_SCENARIOS
from powerflow.conditions.scenario import (
    ConditionsReport,
    EventScenario,
    EventScenarioCategory,
    EventScenarioSummary,
    validate_scenario,
)
from powerflow.core.engine import Engine
from powerflow.core.site_library import SiteLibrary
from powerflow.errors import ConditionError, ProtectedScenarioError
from powerflow.site_config import SiteConfig
from powerflow.storage import ConfigRepository, SiteCategory
from powerflow.storage.names import check_event_scenario_name, check_site_name

logger = logging.getLogger(__name__)

# The problems with a scenario's expected points on a site (empty = fine).
PointCheck = Callable[[EventScenario, SiteConfig], list[str]]


def _no_point_check(_scenario: EventScenario, _config: SiteConfig) -> list[str]:
    return []


class EventScenarioLibrary:
    def __init__(
        self,
        repository: ConfigRepository,
        engine: Engine,
        site_library: SiteLibrary,
        check_points: PointCheck = _no_point_check,
    ) -> None:
        self._repository = repository
        self._engine = engine
        self._site_library = site_library
        self._check_points = check_points

    def _problems(self, scenario: EventScenario, config: SiteConfig) -> list[str]:
        return [*validate_scenario(scenario, config), *self._check_points(scenario, config)]

    async def list(self, site: str) -> list[EventScenarioSummary]:
        config = await self._repository.get_site(check_site_name(site))
        summaries: list[EventScenarioSummary] = []
        for stored in await self._repository.list_event_scenarios(site):
            scenario = await self._repository.get_event_scenario(site, stored.name)
            problems = self._problems(scenario, config)
            summaries.append(
                EventScenarioSummary(
                    name=stored.name,
                    category=stored.category,
                    description=scenario.description,
                    event_count=len(scenario.events),
                    expected_points=scenario.expected_points,
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
        """Validate against the site's stored config, then store. A built-in is read-only."""
        config = await self._repository.get_site(check_site_name(site))
        check_event_scenario_name(name)
        if await self._category(site, name) is EventScenarioCategory.DEFAULT:
            raise ProtectedScenarioError(
                f"{name!r} is a built-in scenario (read-only): save a copy under another name"
            )
        problems = self._problems(scenario, config)
        if problems:
            raise ConditionError("; ".join(problems))
        await self._repository.put_event_scenario(site, name, scenario)
        return scenario

    async def delete(self, site: str, name: str) -> None:
        """Delete a custom scenario; a built-in (default) one can't be deleted."""
        check_site_name(site)
        check_event_scenario_name(name)
        if await self._category(site, name) is EventScenarioCategory.DEFAULT:
            raise ProtectedScenarioError(f"{name!r} is a built-in scenario and can't be deleted")
        await self._repository.delete_event_scenario(site, name)

    async def _category(self, site: str, name: str) -> EventScenarioCategory | None:
        stored = await self._repository.list_event_scenarios(site)
        return next((item.category for item in stored if item.name == name), None)

    async def sync_builtins(self) -> int:
        """Bring the default sites' built-in scenarios in line with the library: add or update
        each (one that doesn't fit a site is skipped and logged) and remove those the library
        no longer has. Returns how many were written or removed."""
        changed = 0
        for site in await self._repository.list_sites():
            if site.category is not SiteCategory.DEFAULT:
                continue
            config = await self._repository.get_site(site.name)
            for stored in await self._repository.list_event_scenarios(site.name):
                retired = stored.name not in BUILTIN_SCENARIOS
                if stored.category is EventScenarioCategory.DEFAULT and retired:
                    await self._repository.delete_event_scenario(site.name, stored.name)
                    changed += 1
            for name, scenario in BUILTIN_SCENARIOS.items():
                problems = self._problems(scenario, config)
                if problems:
                    logger.warning(
                        "built-in scenario %r doesn't fit site %r: %s",
                        name,
                        site.name,
                        "; ".join(problems),
                    )
                    continue
                if await self._repository.sync_builtin_event_scenario(site.name, name, scenario):
                    changed += 1
        return changed

    async def start(self, name: str, at_step: int | None = None) -> ConditionsReport:
        """Play one of the active site's scenarios from the next step, or from engine step
        `at_step`."""
        site = self._site_library.active_site
        scenario = await self._repository.get_event_scenario(site, check_event_scenario_name(name))
        return await self._engine.start_scenario(name, scenario, at_step)
