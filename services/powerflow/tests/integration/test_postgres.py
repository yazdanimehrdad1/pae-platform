"""Postgres: the repository contract, migrations, and the app end to end (seed, edit, restart)."""

import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path

import pytest
from conftest import site_config_dict
from fastapi.testclient import TestClient
from repository_contract import CONTRACT_CHECKS

from integration.conftest import DATABASE_URL, reset_database, run_with_repository
from powerflow.app import create_app
from powerflow.settings import settings
from powerflow.storage import ConfigRepository
from powerflow.storage.postgres import create_database_engine, migrate


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


def test_app_seeds_then_keeps_edits_across_restarts(
    site_config_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asyncio.run(reset_database())
    monkeypatch.setattr(settings, "database_url", DATABASE_URL)
    maps = "/api/sites/reference_2bess_1pv/modbus-maps"
    with TestClient(create_app(site_config_copy)) as first:
        sites = first.get("/api/sites").json()
        assert sites["active"] == "reference_2bess_1pv"  # seeded from the defaults
        assert len(first.get(maps).json()) == 6
        first.post("/api/sim/stop")
        raw = site_config_dict(n_bess=3)
        raw["simulation"]["autostart"] = False
        assert first.put("/api/sites/kept", json=raw).status_code == 200
        assert first.post("/api/sites/kept/activate").status_code == 200
        pv_map = first.get(f"{maps}/pv.pv1").json()
        assert first.put(f"{maps}/pv.pv1", json={**pv_map, "port": 1502}).status_code == 200
    with TestClient(create_app(site_config_copy)) as second:
        assert second.get("/api/sites").json()["active"] == "kept"
        assert len(second.get("/api/config").json()["bess"]) == 3
        assert second.get(f"{maps}/pv.pv1").json()["port"] == 1502
        assert second.delete("/api/sites/reference_2bess_1pv").status_code == 204
        assert second.get(maps).status_code == 404
