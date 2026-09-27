"""SiteLibrary: the stored configuration and switching between sites.

- **Sites, their Modbus maps and the active site** live in the database (ConfigRepository).
- **Profile scenarios** are CSV files (ProfileStore).
- **The shipped defaults** in site_config/ are only a seed: they're imported into an empty
  database at startup, and on demand through `restore_defaults`.

Every write is validated before it's stored. Changing what's running goes through the engine:
activating a site, saving the active site, and saving a profile scenario the active site uses
(hot-reloaded, even while running).
"""

import io
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field, JsonValue

from powerflow.core.engine import Engine, RunState
from powerflow.errors import InUseError, NotFoundError, ProfileError, SiteConfigError
from powerflow.points import POI_ASSET_ID, SITE_ASSET_ID, AssetType
from powerflow.points.modbus_map import ModbusMap, check_map_against_points
from powerflow.profiles import Profile, ProfileKind, parse_profile_csv
from powerflow.site_config import SiteConfig
from powerflow.storage import ConfigRepository, ProfileFolder, ProfileStore
from powerflow.storage.defaults import Defaults, read_defaults
from powerflow.storage.names import check_map_name, check_site_name

SCHEMA_MODELS: dict[str, type[SiteConfig] | type[ModbusMap]] = {
    "site-config": SiteConfig,
    "modbus-map": ModbusMap,
}


class SiteList(BaseModel):
    active: str
    sites: list[str]


class ModbusMapSummary(BaseModel):
    asset: str
    unit_id: int
    port: int
    points: int
    orphaned: bool = Field(description="True if the site no longer has this asset.")


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


class DefaultsInfo(BaseModel):
    active_site: str = Field(description="The site made active on a fresh database.")
    sites: dict[str, list[str]] = Field(description="Default sites and their Modbus map assets.")


class DefaultsRestoreResult(BaseModel):
    overwrite: bool
    sites_written: list[str]
    sites_skipped: list[str] = Field(description="Already stored; pass overwrite=true.")
    maps_written: list[str]
    maps_skipped: list[str]
    active_site_reloaded: bool


async def seed_defaults(repository: ConfigRepository, defaults: Defaults) -> None:
    """Fill an empty database with the default sites, maps and active site."""
    for site in defaults.sites:
        await repository.put_site(site.name, site.config)
        for asset, modbus_map in site.maps.items():
            await repository.put_map(site.name, asset, modbus_map)
    await repository.set_active_site(defaults.active_site)


class SiteLibrary:
    def __init__(
        self,
        repository: ConfigRepository,
        profile_store: ProfileStore,
        engine: Engine,
        defaults_dir: Path,
        active_site: str,
    ) -> None:
        self._repository = repository
        self._profile_store = profile_store
        self._engine = engine
        self._defaults_dir = defaults_dir
        self._active = active_site

    @property
    def active_site(self) -> str:
        return self._active

    # -- sites -----------------------------------------------------------------------------

    async def list_sites(self) -> SiteList:
        return SiteList(active=self._active, sites=await self._repository.list_sites())

    async def get_site(self, name: str) -> SiteConfig:
        return await self._repository.get_site(check_site_name(name))

    async def save_site(self, name: str, config: SiteConfig) -> SiteConfig:
        """Validate and store a site. Saving the active site reloads it, so the simulation must
        be stopped first."""
        check_site_name(name)
        self._check_scenarios(config)
        if name == self._active:
            if self._engine.run_state is not RunState.STOPPED:
                raise InUseError(f"{name!r} is the active site: stop the simulation first")
            await self._engine.replace_config(config)
        await self._repository.put_site(name, config)
        return config

    async def delete_site(self, name: str) -> None:
        if check_site_name(name) == self._active:
            raise InUseError(f"{name!r} is the active site; activate another one first")
        await self._repository.delete_site(name)

    async def activate(self, name: str) -> SiteConfig:
        """Load a stored site into the engine (only while stopped) and make it the site loaded
        at startup."""
        config = await self._repository.get_site(check_site_name(name))
        await self._engine.replace_config(config)
        await self._repository.set_active_site(name)
        self._active = name
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

    # -- Modbus maps (per site) -------------------------------------------------------------

    async def list_maps(self, site: str) -> list[ModbusMapSummary]:
        config = await self._repository.get_site(check_site_name(site))
        summaries: list[ModbusMapSummary] = []
        for asset in await self._repository.list_maps(site):
            modbus_map = await self._repository.get_map(site, asset)
            summaries.append(
                ModbusMapSummary(
                    asset=asset,
                    unit_id=modbus_map.unit_id,
                    port=modbus_map.port,
                    points=len(modbus_map.points),
                    orphaned=not _asset_in_site(config, modbus_map),
                )
            )
        return summaries

    async def get_map(self, site: str, asset: str) -> ModbusMap:
        return await self._repository.get_map(check_site_name(site), check_map_name(asset))

    async def save_map(self, site: str, asset: str, modbus_map: ModbusMap) -> ModbusMap:
        """Validate a map against the point list and the site, then store it."""
        config = await self._repository.get_site(check_site_name(site))
        check_map_name(asset)
        if modbus_map.asset != asset:
            raise SiteConfigError(f"map is for {modbus_map.asset!r} but was saved as {asset!r}")
        if not _asset_in_site(config, modbus_map):
            raise SiteConfigError(f"site {site!r} has no asset {asset!r}")
        problems = check_map_against_points(modbus_map)
        if problems:
            raise SiteConfigError(f"map doesn't fit the point list: {problems}")
        for other in await self._repository.list_maps(site):
            if other == asset:
                continue
            other_map = await self._repository.get_map(site, other)
            if (other_map.port, other_map.unit_id) == (modbus_map.port, modbus_map.unit_id):
                raise SiteConfigError(
                    f"unit_id {modbus_map.unit_id} on port {modbus_map.port} is already {other}"
                )
        await self._repository.put_map(site, asset, modbus_map)
        return modbus_map

    async def delete_map(self, site: str, asset: str) -> None:
        await self._repository.delete_map(check_site_name(site), check_map_name(asset))

    # -- schemas (from code) ---------------------------------------------------------------

    def list_schemas(self) -> list[str]:
        return sorted(SCHEMA_MODELS)

    def get_schema(self, name: str) -> dict[str, JsonValue]:
        if name not in SCHEMA_MODELS:
            raise NotFoundError(f"no schema {name!r}")
        return SCHEMA_MODELS[name].model_json_schema()

    # -- defaults (site_config/, read-only seed) --------------------------------------------

    def defaults_info(self) -> DefaultsInfo:
        defaults = read_defaults(self._defaults_dir)
        return DefaultsInfo(
            active_site=defaults.active_site,
            sites={site.name: sorted(site.maps) for site in defaults.sites},
        )

    async def restore_defaults(self, overwrite: bool) -> DefaultsRestoreResult:
        """Import the default sites and maps. Without overwrite, stored items are kept; with
        overwrite they're replaced (the simulation must be stopped, since the active site may
        change). The active-site choice is left as it is."""
        if overwrite and self._engine.run_state is not RunState.STOPPED:
            raise InUseError("stop the simulation before restoring defaults with overwrite")
        defaults = read_defaults(self._defaults_dir)
        stored_sites = set(await self._repository.list_sites())
        result = DefaultsRestoreResult(
            overwrite=overwrite,
            sites_written=[],
            sites_skipped=[],
            maps_written=[],
            maps_skipped=[],
            active_site_reloaded=False,
        )
        for site in defaults.sites:
            if site.name in stored_sites and not overwrite:
                result.sites_skipped.append(site.name)
            else:
                await self._repository.put_site(site.name, site.config)
                result.sites_written.append(site.name)
            stored_maps = set(await self._repository.list_maps(site.name))
            for asset, modbus_map in site.maps.items():
                label = f"{site.name}/{asset}"
                if asset in stored_maps and not overwrite:
                    result.maps_skipped.append(label)
                else:
                    await self._repository.put_map(site.name, asset, modbus_map)
                    result.maps_written.append(label)
        if self._active in result.sites_written:
            await self._engine.replace_config(await self._repository.get_site(self._active))
            result.active_site_reloaded = True
        return result

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
            site
            for site in await self._repository.list_sites()
            if scenario in _scenarios_used(await self._repository.get_site(site), folder)
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


def _asset_in_site(config: SiteConfig, modbus_map: ModbusMap) -> bool:
    match modbus_map.asset_type:
        case AssetType.BESS:
            return any(bess.id == modbus_map.asset_id for bess in config.bess)
        case AssetType.PV:
            return any(pv.id == modbus_map.asset_id for pv in config.pv)
        case AssetType.LOAD:
            return any(load.id == modbus_map.asset_id for load in config.loads)
        case AssetType.POI:
            return modbus_map.asset_id == POI_ASSET_ID
        case AssetType.SITE:
            return modbus_map.asset_id == SITE_ASSET_ID


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
