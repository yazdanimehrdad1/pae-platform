"""SiteLibrary: the stored sites and switching between them.

- **Sites and the active site** live in the database (ConfigRepository), the only store for them.
  A fresh database gets the default sites from a data migration (0003_default_sites.sql); they
  are category `default` and can't be deleted (they can be edited).
- **Profile scenarios** are CSV files (ProfileStore).

Every write is validated before it's stored. Changing what's running goes through the engine:
activating a site, saving the active site, and saving a profile scenario the active site uses
(hot-reloaded, even while running). After the engine's config is replaced, `on_config_replaced`
runs (the app restarts the protocol interfaces there).
"""

import io
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pandas as pd
from pydantic import BaseModel, Field, JsonValue

from powerflow.core.engine import Engine, RunState
from powerflow.errors import InUseError, NotFoundError, ProfileError, ProtectedSiteError
from powerflow.profiles import Profile, ProfileKind, parse_profile_csv
from powerflow.site_config import SiteConfig
from powerflow.storage import (
    ConfigRepository,
    ProfileFolder,
    ProfileStore,
    SiteCategory,
    StoredSite,
)
from powerflow.storage.names import check_site_name

SCHEMA_MODELS: dict[str, type[SiteConfig]] = {"site-config": SiteConfig}

ConfigReplacedHook = Callable[[SiteConfig], Awaitable[None]]


class SiteList(BaseModel):
    active: str = Field(description="The site the simulator is running now.")
    stored_active: str | None = Field(
        description="The database's active-site choice (loaded at startup). Differs from "
        "`active` only when the ACTIVE_SITE setting overrides it for this run."
    )
    sites: list[StoredSite]


class ProfileScenarios(BaseModel):
    load: list[str]
    pv: list[str]


class ProfileSaveResult(BaseModel):
    folder: ProfileFolder
    scenario: str
    rows: int
    start: datetime
    end: datetime
    columns: list[str]
    reloaded_assets: list[str] = Field(description="Active-site assets now using the new data.")


async def _nothing(_config: SiteConfig) -> None:
    """Default config-replaced hook."""


class SiteLibrary:
    def __init__(
        self,
        repository: ConfigRepository,
        profile_store: ProfileStore,
        engine: Engine,
        active_site: str,
        on_config_replaced: ConfigReplacedHook = _nothing,
    ) -> None:
        self._repository = repository
        self._profile_store = profile_store
        self._engine = engine
        self._active = active_site
        self.on_config_replaced = on_config_replaced

    @property
    def active_site(self) -> str:
        return self._active

    # -- sites -----------------------------------------------------------------------------

    async def list_sites(self) -> SiteList:
        return SiteList(
            active=self._active,
            stored_active=await self._repository.get_active_site(),
            sites=await self._repository.list_sites(),
        )

    async def get_site(self, name: str) -> SiteConfig:
        return await self._repository.get_site(check_site_name(name))

    async def save_site(self, name: str, config: SiteConfig) -> SiteConfig:
        """Validate and store a site. Saving the active site reloads it (stored first, then
        loaded), so the simulation must be stopped first."""
        check_site_name(name)
        self._check_scenarios(config)
        is_active = name == self._active
        if is_active and self._engine.run_state is not RunState.STOPPED:
            raise InUseError(f"{name!r} is the active site: stop the simulation first")
        await self._repository.put_site(name, config)
        if is_active:
            await self._engine.replace_config(config)
            await self.on_config_replaced(config)
        return config

    async def delete_site(self, name: str) -> None:
        """Delete a stored custom site. Default sites, the running site and the database's
        active-site choice (the one loaded at startup) can't be deleted."""
        check_site_name(name)
        stored = {site.name: site.category for site in await self._repository.list_sites()}
        if stored.get(name) is SiteCategory.DEFAULT:
            raise ProtectedSiteError(f"{name!r} is a default site and can't be deleted")
        if name in (self._active, await self._repository.get_active_site()):
            raise InUseError(f"{name!r} is the active site; activate another one first")
        await self._repository.delete_site(name)

    async def activate(self, name: str) -> SiteConfig:
        """Load a stored site into the engine (only while stopped) and make it the site loaded
        at startup."""
        config = await self._repository.get_site(check_site_name(name))
        await self._engine.replace_config(config)
        await self._repository.set_active_site(name)
        self._active = name
        await self.on_config_replaced(config)
        return config

    def _check_scenarios(self, config: SiteConfig) -> None:
        load_scenarios = self._profile_store.list_profiles(ProfileFolder.LOAD)
        pv_scenarios = self._profile_store.list_profiles(ProfileFolder.PV)
        missing = [
            f"load/{load.profile.scenario}"
            for load in config.loads
            if load.profile.scenario not in load_scenarios
        ] + [
            f"pv/{pv.availability.scenario}"
            for pv in config.pv
            if pv.availability.scenario not in pv_scenarios
        ]
        if missing:
            raise ProfileError(f"unknown profile scenario(s): {missing}")

    # -- schemas (from code) ---------------------------------------------------------------

    def list_schemas(self) -> list[str]:
        return sorted(SCHEMA_MODELS)

    def get_schema(self, name: str) -> dict[str, JsonValue]:
        if name not in SCHEMA_MODELS:
            raise NotFoundError(f"no schema {name!r}")
        return SCHEMA_MODELS[name].model_json_schema()

    # -- profiles (CSV files for now) --------------------------------------------------------

    def list_profiles(self) -> ProfileScenarios:
        return ProfileScenarios(
            load=self._profile_store.list_profiles(ProfileFolder.LOAD),
            pv=self._profile_store.list_profiles(ProfileFolder.PV),
        )

    def read_profile(self, folder: ProfileFolder, scenario: str) -> str:
        return self._profile_store.read_profile_text(folder, scenario)

    async def delete_profile(self, folder: ProfileFolder, scenario: str) -> None:
        """Delete a scenario that no stored site uses."""
        self._profile_store.profile_path(folder, scenario)  # 404 before the usage scan
        users = [
            site.name
            for site in await self._repository.list_sites()
            if scenario in _scenarios_used(await self._repository.get_site(site.name), folder)
        ]
        if users:
            raise InUseError(f"{folder}/{scenario} is used by site(s) {users}")
        self._profile_store.delete_profile(folder, scenario)

    async def save_profile(
        self, folder: ProfileFolder, scenario: str, csv_text: str
    ) -> ProfileSaveResult:
        """Validate and store a profile scenario, then hot-reload it into active-site assets
        that use it."""
        profile = self._validate_profile(folder, scenario, csv_text)
        self._profile_store.write_profile_text(folder, scenario, csv_text)
        reloaded = await self._engine.reload_scenario(folder, scenario)
        return ProfileSaveResult(
            folder=folder,
            scenario=scenario,
            rows=len(profile.times_s),
            start=datetime.fromtimestamp(profile.start_s, tz=UTC),
            end=datetime.fromtimestamp(profile.end_s, tz=UTC),
            columns=list(profile.columns),
            reloaded_assets=reloaded,
        )

    def _validate_profile(self, folder: ProfileFolder, scenario: str, csv_text: str) -> Profile:
        if folder is ProfileFolder.LOAD:
            return parse_profile_csv(csv_text, ProfileKind.LOAD, loop=True)
        # A PV scenario may carry p_kw (ac_kw source), ghi_wm2 (irradiance source) or both;
        # every kind an active-site PV using this scenario needs must be present.
        header = _csv_header(csv_text)
        kinds = [
            kind
            for kind, column in (
                (ProfileKind.PV_AC, "p_kw"),
                (ProfileKind.PV_IRRADIANCE, "ghi_wm2"),
            )
            if column in header
        ]
        if not kinds:
            raise ProfileError("a PV profile needs a p_kw and/or a ghi_wm2 column")
        needed = {
            ProfileKind.for_pv(pv.config.availability.source)
            for pv in self._engine.runtime.pv.values()
            if pv.config.availability.scenario == scenario
        }
        if needed - set(kinds):
            missing = sorted(str(kind) for kind in needed - set(kinds))
            raise ProfileError(f"the active site uses {scenario!r} as {missing}; column missing")
        profiles = [parse_profile_csv(csv_text, kind, loop=True) for kind in kinds]
        return profiles[0]


def _scenarios_used(config: SiteConfig, folder: ProfileFolder) -> set[str]:
    if folder is ProfileFolder.LOAD:
        return {load.profile.scenario for load in config.loads}
    return {pv.availability.scenario for pv in config.pv}


def _csv_header(csv_text: str) -> list[str]:
    try:
        frame = pd.read_csv(io.StringIO(csv_text), nrows=0)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise ProfileError(f"can't parse CSV: {error}") from error
    return [str(column).strip() for column in frame.columns]
