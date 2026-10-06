"""Postgres: the repository contract, the migrations (including the default sites they insert),
and the app end to end (fresh database, edit, restart)."""

import asyncio
from collections.abc import Callable, Coroutine

import pytest
from conftest import (
    DEFAULT_ACTIVE_SITE,
    DEFAULT_SITE_LIST,
    DEFAULT_SITE_NAMES,
    PROFILES_DIR,
    site_config_dict,
)
from fastapi.testclient import TestClient
from repository_contract import CONTRACT_CHECKS
from sqlalchemy import text

from integration.conftest import DATABASE_URL, reset_database, run_with_repository
from powerflow.app import create_app
from powerflow.settings import settings
from powerflow.storage import ConfigRepository, SiteCategory, StoredSite
from powerflow.storage.postgres import PostgresConfigRepository, create_database_engine, migrate
from powerflow.storage.seed_data import default_sites


@pytest.mark.parametrize("check", CONTRACT_CHECKS, ids=lambda check: check.__name__)
def test_postgres_repository_contract(
    check: Callable[[ConfigRepository], Coroutine[object, object, None]],
) -> None:
    run_with_repository(check)


def test_migrations_are_idempotent() -> None:
    async def body() -> list[str]:
        await reset_database()
        engine = create_database_engine(DATABASE_URL)
        try:
            return await migrate(engine)
        finally:
            await engine.dispose()

    assert asyncio.run(body()) == []  # reset_database already applied them


def test_fresh_database_has_the_default_sites() -> None:
    async def body() -> None:
        await reset_database(empty=False)
        repository = PostgresConfigRepository(create_database_engine(DATABASE_URL))
        try:
            sites = await repository.list_sites()
            assert [site.name for site in sites] == DEFAULT_SITE_NAMES
            assert {site.category for site in sites} == {SiteCategory.DEFAULT}
            assert await repository.get_active_site() == DEFAULT_ACTIVE_SITE
            for name, config in default_sites().items():
                assert await repository.get_site(name) == config
        finally:
            await repository.close()

    asyncio.run(body())


def test_default_sites_migration_refreshes_a_stale_database() -> None:
    """A database seeded before the meters existed gets the current default sites once."""

    async def body() -> None:
        await reset_database(empty=False)
        engine = create_database_engine(DATABASE_URL)
        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(
                    "UPDATE sites SET config = config - 'meters' WHERE name = '2bess_1pv'"
                )
                await connection.exec_driver_sql(
                    "DELETE FROM schema_migrations WHERE version = '0003_default_sites'"
                )
            assert await migrate(engine) == ["0003_default_sites"]
            repository = PostgresConfigRepository(engine)
            site = await repository.get_site("2bess_1pv")
            assert [meter.id for meter in site.meters] == ["m_bess1", "m_bess2", "m_pv1"]
        finally:
            await engine.dispose()

    asyncio.run(body())


OLD_DEFAULT_NAMES = {
    "2bess_1pv": "reference_2bess_1pv",
    "1bess_1pv": "small_1bess_1pv",
    "3bess_2pv": "three_bess_two_pv",
}


def test_site_categories_migration_renames_the_old_default_sites() -> None:
    """A database that ran 0003 under the old site names (before categories existed) gets the
    new names, its active site follows, and the defaults are marked `default`."""

    async def body() -> None:
        await reset_database(empty=False)
        engine = create_database_engine(DATABASE_URL)
        try:
            async with engine.begin() as connection:
                for name, old_name in OLD_DEFAULT_NAMES.items():
                    await connection.exec_driver_sql(
                        f"UPDATE sites SET name = '{old_name}' WHERE name = '{name}'"
                    )
                await connection.exec_driver_sql(
                    'UPDATE app_state SET value = \'{"site": "reference_2bess_1pv"}\''
                )
                await connection.exec_driver_sql("ALTER TABLE sites DROP COLUMN category")
                await connection.exec_driver_sql(
                    "INSERT INTO sites (name, config) SELECT 'mine', config FROM sites LIMIT 1"
                )
                await connection.exec_driver_sql(
                    "DELETE FROM schema_migrations WHERE version = '0004_site_categories'"
                )
            assert await migrate(engine) == ["0004_site_categories"]
            repository = PostgresConfigRepository(engine)
            assert await repository.list_sites() == [
                StoredSite(name="1bess_1pv", category=SiteCategory.DEFAULT),
                StoredSite(name="2bess_1pv", category=SiteCategory.DEFAULT),
                StoredSite(name="3bess_2pv", category=SiteCategory.DEFAULT),
                StoredSite(name="mine", category=SiteCategory.CUSTOM),
            ]
            assert await repository.get_active_site() == "2bess_1pv"
        finally:
            await engine.dispose()

    asyncio.run(body())


def test_sites_are_stored_with_every_field() -> None:
    """Defaults are written out, so a later change to a code default can't change a stored site."""

    async def body() -> None:
        await reset_database()
        engine = create_database_engine(DATABASE_URL)
        try:
            repository = PostgresConfigRepository(engine)
            await repository.put_site("alpha", default_sites()["1bess_1pv"])
            async with engine.connect() as connection:
                stored = await connection.scalar(
                    text("SELECT config FROM sites WHERE name = 'alpha'")
                )
            assert {"grid", "simulation", "interfaces", "collectors"} <= set(stored)
            assert "soc_min_pct" in stored["bess"][0]["battery"]
        finally:
            await engine.dispose()

    asyncio.run(body())


def test_app_keeps_edits_across_restarts(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(reset_database(empty=False))
    monkeypatch.setattr(settings, "database_url", DATABASE_URL)
    with TestClient(create_app(PROFILES_DIR)) as first:
        sites = first.get("/api/sites").json()
        assert sites["active"] == DEFAULT_ACTIVE_SITE  # from the migration
        assert sites["sites"] == DEFAULT_SITE_LIST
        first.post("/api/sim/stop")
        raw = site_config_dict(n_bess=3)
        raw["simulation"]["autostart"] = False
        assert first.put("/api/sites/kept", json=raw).status_code == 200
        assert first.post("/api/sites/kept/activate").status_code == 200
    with TestClient(create_app(PROFILES_DIR)) as second:
        assert second.get("/api/sites").json()["active"] == "kept"
        assert len(second.get("/api/config").json()["bess"]) == 3
        response = second.delete("/api/sites/2bess_1pv")
        assert response.status_code == 409 and "default site" in response.json()["detail"]
