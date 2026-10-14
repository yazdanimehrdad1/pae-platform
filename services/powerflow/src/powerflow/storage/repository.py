"""ConfigRepository: where sites and the active site are stored. The database is the only store:
a fresh one gets the default sites from a data migration (migrations/0003_default_sites.sql).

Production uses PostgresConfigRepository (storage/postgres.py). InMemoryConfigRepository has the
same behaviour without a database, for unit tests; tests/integration runs the same contract
tests against Postgres. Name rules are enforced by the caller (SiteLibrary); a repository only
stores what it's given.
"""

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel, Field

from powerflow.conditions.scenario import EventScenario, EventScenarioCategory
from powerflow.errors import NotFoundError
from powerflow.site_config import SiteConfig
from powerflow.storage.seed_data import default_active_site, default_sites


class SiteCategory(StrEnum):
    DEFAULT = "default"  # ships with powerflow (a data migration); can't be deleted
    CUSTOM = "custom"  # created through the API


class StoredSite(BaseModel):
    name: str
    category: SiteCategory = Field(
        description="`default` sites ship with powerflow and can't be deleted (they can be "
        "edited); every site created through the API is `custom`."
    )


class StoredEventScenario(BaseModel):
    name: str
    category: EventScenarioCategory


class ConfigRepository(ABC):
    @abstractmethod
    async def list_sites(self) -> list[StoredSite]:
        """Sorted by name."""

    @abstractmethod
    async def get_site(self, name: str) -> SiteConfig:
        """Raises NotFoundError."""

    @abstractmethod
    async def put_site(self, name: str, config: SiteConfig) -> None:
        """Create (category custom) or replace (the category is kept)."""

    @abstractmethod
    async def delete_site(self, name: str) -> None:
        """Raises NotFoundError. Deleting the active site clears the active-site choice."""

    @abstractmethod
    async def get_active_site(self) -> str | None: ...

    @abstractmethod
    async def set_active_site(self, name: str) -> None:
        """Raises NotFoundError if the site doesn't exist."""

    @abstractmethod
    async def list_event_scenarios(self, site: str) -> list[StoredEventScenario]:
        """Sorted by name. Raises NotFoundError if the site doesn't exist."""

    @abstractmethod
    async def get_event_scenario(self, site: str, name: str) -> EventScenario:
        """Raises NotFoundError."""

    @abstractmethod
    async def put_event_scenario(self, site: str, name: str, scenario: EventScenario) -> None:
        """Create (category custom) or replace (the category is kept). Raises NotFoundError if
        the site doesn't exist."""

    @abstractmethod
    async def sync_builtin_event_scenario(
        self, site: str, name: str, scenario: EventScenario
    ) -> bool:
        """Create a built-in (category default), or replace a stored built-in of that name; a
        custom scenario of that name is left alone. True if anything was written. Raises
        NotFoundError if the site doesn't exist."""

    @abstractmethod
    async def delete_event_scenario(self, site: str, name: str) -> None:
        """Raises NotFoundError."""

    @abstractmethod
    async def close(self) -> None:
        """Release connections."""


class InMemoryConfigRepository(ConfigRepository):
    def __init__(self) -> None:
        self._sites: dict[str, SiteConfig] = {}
        self._categories: dict[str, SiteCategory] = {}
        self._active: str | None = None
        self._event_scenarios: dict[tuple[str, str], EventScenario] = {}
        self._scenario_categories: dict[tuple[str, str], EventScenarioCategory] = {}

    @classmethod
    def with_default_sites(cls) -> "InMemoryConfigRepository":
        """Holding what a freshly migrated Postgres holds: the default sites and active site."""
        repository = cls()
        repository._sites = default_sites()
        repository._categories = dict.fromkeys(repository._sites, SiteCategory.DEFAULT)
        repository._active = default_active_site()
        return repository

    async def list_sites(self) -> list[StoredSite]:
        return [
            StoredSite(name=name, category=self._categories[name]) for name in sorted(self._sites)
        ]

    async def get_site(self, name: str) -> SiteConfig:
        self._require_site(name)
        return self._sites[name]

    async def put_site(self, name: str, config: SiteConfig) -> None:
        self._sites[name] = config
        self._categories.setdefault(name, SiteCategory.CUSTOM)

    async def delete_site(self, name: str) -> None:
        self._require_site(name)
        del self._sites[name]
        del self._categories[name]
        for key in [key for key in self._event_scenarios if key[0] == name]:
            del self._event_scenarios[key]
            del self._scenario_categories[key]
        if self._active == name:
            self._active = None

    async def get_active_site(self) -> str | None:
        return self._active

    async def set_active_site(self, name: str) -> None:
        self._require_site(name)
        self._active = name

    async def list_event_scenarios(self, site: str) -> list[StoredEventScenario]:
        self._require_site(site)
        return [
            StoredEventScenario(name=name, category=self._scenario_categories[(site, name)])
            for name in sorted(
                name for site_name, name in self._event_scenarios if site_name == site
            )
        ]

    async def get_event_scenario(self, site: str, name: str) -> EventScenario:
        if (site, name) not in self._event_scenarios:
            raise NotFoundError(f"no event scenario {name!r} for site {site!r}")
        return self._event_scenarios[(site, name)]

    async def put_event_scenario(self, site: str, name: str, scenario: EventScenario) -> None:
        self._require_site(site)
        self._event_scenarios[(site, name)] = scenario
        self._scenario_categories.setdefault((site, name), EventScenarioCategory.CUSTOM)

    async def sync_builtin_event_scenario(
        self, site: str, name: str, scenario: EventScenario
    ) -> bool:
        self._require_site(site)
        key = (site, name)
        if self._scenario_categories.get(key) is EventScenarioCategory.CUSTOM:
            return False
        if self._event_scenarios.get(key) == scenario:
            return False
        self._event_scenarios[key] = scenario
        self._scenario_categories[(site, name)] = EventScenarioCategory.DEFAULT
        return True

    async def delete_event_scenario(self, site: str, name: str) -> None:
        if (site, name) not in self._event_scenarios:
            raise NotFoundError(f"no event scenario {name!r} for site {site!r}")
        del self._event_scenarios[(site, name)]
        del self._scenario_categories[(site, name)]

    async def close(self) -> None:
        """Nothing to release."""

    def _require_site(self, name: str) -> None:
        if name not in self._sites:
            raise NotFoundError(f"no site {name!r}")
