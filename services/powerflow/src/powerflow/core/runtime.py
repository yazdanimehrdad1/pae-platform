"""SiteRuntime: everything built from one SiteConfig (asset parameters, loaded profiles, the
topology and its solver). Replaced as a whole when the config changes."""

from dataclasses import dataclass
from pathlib import Path

from powerflow.errors import NotFoundError, ProfileError, UnknownAssetError
from powerflow.models.bess import BessParams
from powerflow.models.pv import PvParams
from powerflow.network.solver import PowerFlowSolver, SolverFactory
from powerflow.network.topology import Topology, build_topology
from powerflow.profiles import Profile, ProfileKind, load_profile_file
from powerflow.site_config import BessConfig, LoadConfig, PvConfig, SiteConfig
from powerflow.storage import ProfileFolder, ProfileStore


@dataclass
class BessRuntime:
    config: BessConfig
    params: BessParams


@dataclass
class PvRuntime:
    config: PvConfig
    params: PvParams
    profile: Profile


@dataclass
class LoadRuntime:
    config: LoadConfig
    profile: Profile


@dataclass
class SiteRuntime:
    config: SiteConfig
    bess: dict[str, BessRuntime]
    pv: dict[str, PvRuntime]
    loads: dict[str, LoadRuntime]
    topology: Topology
    solver: PowerFlowSolver

    @classmethod
    def build(
        cls, config: SiteConfig, profile_store: ProfileStore, solver_factory: SolverFactory
    ) -> "SiteRuntime":
        """Load every profile scenario from the profile store and build the solver. Raises
        ProfileError (also for an unknown scenario)."""
        pv = {
            entry.id: PvRuntime(
                config=entry,
                params=PvParams.from_config(entry),
                profile=load_pv_profile(profile_store, entry),
            )
            for entry in config.pv
        }
        loads = {
            entry.id: LoadRuntime(config=entry, profile=load_load_profile(profile_store, entry))
            for entry in config.loads
        }
        bess = {
            entry.id: BessRuntime(config=entry, params=BessParams.from_config(entry))
            for entry in config.bess
        }
        topology = build_topology(config)
        return cls(
            config=config,
            bess=bess,
            pv=pv,
            loads=loads,
            topology=topology,
            solver=solver_factory(topology),
        )

    def bess_asset(self, asset_id: str) -> BessRuntime:
        if asset_id not in self.bess:
            raise UnknownAssetError(f"no BESS {asset_id!r}")
        return self.bess[asset_id]

    def pv_asset(self, asset_id: str) -> PvRuntime:
        if asset_id not in self.pv:
            raise UnknownAssetError(f"no PV {asset_id!r}")
        return self.pv[asset_id]

    def load_asset(self, asset_id: str) -> LoadRuntime:
        if asset_id not in self.loads:
            raise UnknownAssetError(f"no load {asset_id!r}")
        return self.loads[asset_id]


def _scenario_path(profile_store: ProfileStore, folder: ProfileFolder, scenario: str) -> Path:
    try:
        return profile_store.profile_path(folder, scenario)
    except NotFoundError as error:
        raise ProfileError(f"unknown {folder} profile scenario {scenario!r}") from error


def load_pv_profile(profile_store: ProfileStore, config: PvConfig) -> Profile:
    availability = config.availability
    return load_profile_file(
        _scenario_path(profile_store, ProfileFolder.PV, availability.scenario),
        ProfileKind.for_pv(availability.source),
        availability.loop,
        availability.scale,
    )


def load_load_profile(profile_store: ProfileStore, config: LoadConfig) -> Profile:
    return load_profile_file(
        _scenario_path(profile_store, ProfileFolder.LOAD, config.profile.scenario),
        ProfileKind.LOAD,
        config.profile.loop,
        config.profile.scale,
    )
