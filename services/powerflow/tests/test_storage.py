"""Storage: the repository contract (in memory), the profile CSV store, the defaults reader."""

import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path

import pytest
from conftest import DEFAULT_SITE_NAMES
from repository_contract import CONTRACT_CHECKS

from powerflow.errors import InvalidNameError, NotFoundError, SiteConfigError
from powerflow.storage import (
    ConfigRepository,
    InMemoryConfigRepository,
    ProfileFolder,
    ProfileStore,
)
from powerflow.storage.defaults import read_defaults


@pytest.mark.parametrize("check", CONTRACT_CHECKS, ids=lambda check: check.__name__)
def test_in_memory_repository_contract(
    check: Callable[[ConfigRepository], Coroutine[object, object, None]],
) -> None:
    asyncio.run(check(InMemoryConfigRepository()))


class TestProfileStore:
    @pytest.fixture
    def store(self, site_config_copy: Path) -> ProfileStore:
        return ProfileStore(site_config_copy / "profiles")

    def test_lists_and_reads(self, store: ProfileStore) -> None:
        assert "typical" in store.list_profiles(ProfileFolder.LOAD)
        assert store.read_profile_text(ProfileFolder.PV, "clear_sky_high").startswith("timestamp,")

    def test_write_is_atomic_and_leaves_no_temp_files(self, store: ProfileStore) -> None:
        store.write_profile_text(ProfileFolder.LOAD, "tiny", "timestamp,p_kw,q_kvar")
        assert store.read_profile_text(ProfileFolder.LOAD, "tiny") == "timestamp,p_kw,q_kvar\n"
        assert list(store.root.rglob(".tmp-*")) == []

    def test_delete(self, store: ProfileStore) -> None:
        store.write_profile_text(ProfileFolder.PV, "tiny", "timestamp,p_kw\n")
        store.delete_profile(ProfileFolder.PV, "tiny")
        assert "tiny" not in store.list_profiles(ProfileFolder.PV)
        with pytest.raises(NotFoundError):
            store.delete_profile(ProfileFolder.PV, "tiny")

    @pytest.mark.parametrize("name", ["../escape", "a/b", "UPPER", "", "..", "nul", "com1"])
    def test_bad_names_are_rejected(self, store: ProfileStore, name: str) -> None:
        with pytest.raises(InvalidNameError):
            store.write_profile_text(ProfileFolder.LOAD, name, "timestamp,p_kw\n")

    def test_names_match_exactly(self, store: ProfileStore) -> None:
        with pytest.raises((NotFoundError, InvalidNameError)):
            store.profile_path(ProfileFolder.LOAD, "Typical")


class TestDefaults:
    def test_reads_every_site_with_its_maps(self, site_config_copy: Path) -> None:
        defaults = read_defaults(site_config_copy)
        assert [site.name for site in defaults.sites] == DEFAULT_SITE_NAMES
        assert defaults.active_site == "reference_2bess_1pv"
        reference = next(site for site in defaults.sites if site.name == "reference_2bess_1pv")
        assert "pv.pv1" in reference.maps and "poi.meter" in reference.maps

    def test_bad_default_is_reported(self, site_config_copy: Path) -> None:
        (site_config_copy / "sites" / "broken.json").write_text('{"grid": {"vn_kv": -1}}')
        with pytest.raises(SiteConfigError, match="broken"):
            read_defaults(site_config_copy)

    def test_active_must_exist(self, site_config_copy: Path) -> None:
        (site_config_copy / "active.json").write_text('{"site": "missing"}')
        with pytest.raises(SiteConfigError, match="missing"):
            read_defaults(site_config_copy)
