"""Storage: the repository contract (in memory), the profile CSV store, the default sites
(read from the data migration), and the migration statement splitter."""

import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path

import pytest
from conftest import DEFAULT_SITE_NAMES
from repository_contract import CONTRACT_CHECKS

from powerflow.errors import InvalidNameError, NotFoundError
from powerflow.storage import (
    ConfigRepository,
    InMemoryConfigRepository,
    ProfileFolder,
    ProfileStore,
    SiteCategory,
)
from powerflow.storage.postgres import MIGRATIONS_DIR, _statements
from powerflow.storage.seed_data import default_active_site, default_sites


@pytest.mark.parametrize("check", CONTRACT_CHECKS, ids=lambda check: check.__name__)
def test_in_memory_repository_contract(
    check: Callable[[ConfigRepository], Coroutine[object, object, None]],
) -> None:
    asyncio.run(check(InMemoryConfigRepository()))


class TestProfileStore:
    @pytest.fixture
    def store(self, profiles_copy: Path) -> ProfileStore:
        return ProfileStore(profiles_copy)

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


class TestDefaultSites:
    def test_the_migration_seeds_valid_sites_and_an_active_one(self) -> None:
        sites = default_sites()
        assert sorted(sites) == DEFAULT_SITE_NAMES
        assert default_active_site() in sites
        reference = sites["2bess_1pv"]
        assert [meter.id for meter in reference.meters] == ["m_bess1", "m_bess2", "m_pv1"]
        assert reference.interfaces.modbus.enabled

    def test_in_memory_repository_starts_like_a_migrated_database(self) -> None:
        repository = InMemoryConfigRepository.with_default_sites()
        sites = asyncio.run(repository.list_sites())
        assert [site.name for site in sites] == DEFAULT_SITE_NAMES
        assert {site.category for site in sites} == {SiteCategory.DEFAULT}
        assert asyncio.run(repository.get_active_site()) == default_active_site()


class TestMigrationStatements:
    def test_semicolons_inside_dollar_quotes_stay_in_their_statement(self) -> None:
        sql = "-- a comment; ignored\nINSERT INTO t VALUES ($x$a;b$x$);\nSELECT 1;"
        assert _statements(sql) == ["INSERT INTO t VALUES ($x$a;b$x$)", "SELECT 1"]

    def test_the_default_sites_migration_is_one_statement_per_insert(self) -> None:
        statements = _statements((MIGRATIONS_DIR / "0003_default_sites.sql").read_text("utf-8"))
        assert len(statements) == len(DEFAULT_SITE_NAMES) + 1  # the sites + the active site
