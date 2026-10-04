"""HTTP API through FastAPI's TestClient (with the lifespan, so the real engine runs).

Every app gets an in-memory configuration repository (the Postgres one is covered by
tests/integration) holding the default sites, as a freshly migrated database does, plus a test
site made active, and its own copy of profiles/, so nothing writes the repo."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import DEFAULT_ACTIVE_SITE, DEFAULT_SITE_LIST, site_config_dict
from fastapi.testclient import TestClient

from powerflow.app import create_app
from powerflow.settings import settings
from powerflow.site_config import SiteConfig
from powerflow.storage import InMemoryConfigRepository

TEST_SITE = "test_site"


def site_names(client: TestClient) -> list[str]:
    return [site["name"] for site in client.get("/api/sites").json()["sites"]]


def repository_with_test_site(raw: dict[str, Any]) -> InMemoryConfigRepository:
    """The default sites, plus raw stored as test_site and made the active site."""
    repository = InMemoryConfigRepository.with_default_sites()

    async def fill() -> None:
        await repository.put_site(TEST_SITE, SiteConfig.model_validate(raw))
        await repository.set_active_site(TEST_SITE)

    asyncio.run(fill())
    return repository


@pytest.fixture
def repository() -> InMemoryConfigRepository:
    return repository_with_test_site(site_config_dict(n_bess=2))


@pytest.fixture
def client(profiles_copy: Path, repository: InMemoryConfigRepository) -> Iterator[TestClient]:
    with TestClient(create_app(profiles_copy, repository)) as test_client:
        yield test_client


def step(client: TestClient, count: int = 1) -> dict[str, Any]:
    response = client.post("/api/sim/step", params={"count": count})
    assert response.status_code == 200, response.text
    return response.json()


class TestHealthAndStatus:
    def test_health_and_version(self, client: TestClient) -> None:
        assert client.get("/api/health").json() == {
            "ok": True,
            "state": "stopped",
            "interfaces": ["http"],
            "interface_errors": {},
        }
        version = client.get("/api/version").json()
        assert version["service"] == "powerflow" and version["pandapower_version"]

    def test_status(self, client: TestClient) -> None:
        status = client.get("/api/sim/status").json()
        assert status["state"] == "stopped" and status["step_id"] == 0 and status["test_mode"]
        assert status["last_converged"] is None


class TestSimulationControl:
    def test_step_returns_snapshot_and_advances(self, client: TestClient) -> None:
        snapshot = step(client, 3)
        assert snapshot["step_id"] == 3 and snapshot["converged"] is True
        assert client.get("/api/sim/status").json()["step_id"] == 3

    def test_step_count_validated(self, client: TestClient) -> None:
        assert client.post("/api/sim/step", params={"count": 0}).status_code == 422

    def test_state_conflicts(self, client: TestClient) -> None:
        assert client.post("/api/sim/pause").status_code == 409
        assert client.get("/api/measurements/latest").status_code == 409
        assert client.post("/api/sim/start").json()["state"] == "running"
        assert client.post("/api/sim/step").status_code == 409
        assert client.post(f"/api/sites/{TEST_SITE}/activate").status_code == 409
        assert client.post("/api/sim/pause").json()["state"] == "paused"
        assert client.post("/api/sim/stop").json()["state"] == "stopped"

    def test_reset(self, client: TestClient) -> None:
        step(client, 2)
        status = client.post("/api/sim/reset").json()
        assert status["step_id"] == 0 and status["history_count"] == 0

    def test_step_needs_test_mode(self, profiles_copy: Path) -> None:
        raw = site_config_dict()
        raw["simulation"]["test_mode"] = False
        repository = repository_with_test_site(raw)
        with TestClient(create_app(profiles_copy, repository)) as test_client:
            response = test_client.post("/api/sim/step")
            assert response.status_code == 409 and "test_mode" in response.json()["detail"]


class TestSetpoints:
    def test_bess_setpoint_accepted(self, client: TestClient) -> None:
        response = client.put("/api/assets/bess/bess1/setpoint", json={"p_kw": 1000, "mode": "pq"})
        assert response.status_code == 200
        body = response.json()
        assert body["accepted"] == {"p_kw": 1000, "q_kvar": 0, "mode": "pq"}
        assert body["clamped"] is False
        snapshot = step(client)
        assert snapshot["bess"][0]["p_kw"] == pytest.approx(1000)
        assert snapshot["bess"][1]["p_kw"] == 0  # the other BESS is untouched

    def test_bess_setpoint_clamped(self, client: TestClient) -> None:
        body = client.put(
            "/api/assets/bess/bess1/setpoint", json={"p_kw": 2500, "q_kvar": 2500, "mode": "pq"}
        ).json()
        assert body["clamped"] is True and body["flags"] == ["S_LIMIT"]
        assert body["accepted"]["p_kw"] == 2500
        assert body["accepted"]["q_kvar"] == pytest.approx((2750**2 - 2500**2) ** 0.5)

    def test_partial_update_keeps_other_fields(self, client: TestClient) -> None:
        client.put("/api/assets/bess/bess1/setpoint", json={"p_kw": 500, "mode": "pq"})
        body = client.put("/api/assets/bess/bess1/setpoint", json={"q_kvar": 100}).json()
        assert body["accepted"] == {"p_kw": 500, "q_kvar": 100, "mode": "pq"}

    @pytest.mark.parametrize(
        "payload",
        [
            {"p_kw": "lots"},
            {"mode": "turbo"},
            {"p_kw": 1, "extra": 2},
        ],
    )
    def test_invalid_bess_setpoints(self, client: TestClient, payload: dict[str, Any]) -> None:
        assert client.put("/api/assets/bess/bess1/setpoint", json=payload).status_code == 422

    def test_pv_setpoint(self, client: TestClient) -> None:
        body = client.put(
            "/api/assets/pv/pv1/setpoint", json={"p_limit_pct": 40, "pf": 0.95}
        ).json()
        assert body["accepted"]["p_limit_kw"] == pytest.approx(1000)
        assert body["accepted"]["q_mode"] == "pf"
        snapshot = step(client)
        assert snapshot["pv"][0]["p_kw"] == pytest.approx(1000)
        assert snapshot["pv"][0]["pf"] == pytest.approx(0.95)

    @pytest.mark.parametrize(
        "payload",
        [
            {"p_limit_kw": 100, "p_limit_pct": 10},
            {"q_kvar": 10, "pf": 0.9},
            {"pf": 0.5},
            {"p_limit_kw": -5},
        ],
    )
    def test_invalid_pv_setpoints(self, client: TestClient, payload: dict[str, Any]) -> None:
        assert client.put("/api/assets/pv/pv1/setpoint", json=payload).status_code == 422

    def test_unknown_asset(self, client: TestClient) -> None:
        assert client.put("/api/assets/bess/nope/setpoint", json={"p_kw": 1}).status_code == 404
        assert client.get("/api/assets/pv/nope").status_code == 404
        assert client.get("/api/assets/load/nope").status_code == 404


class TestAssetsAndPoints:
    def test_assets(self, client: TestClient) -> None:
        assets = client.get("/api/assets").json()
        assert [item["id"] for item in assets["bess"]] == ["bess1", "bess2"]
        bess = client.get("/api/assets/bess/bess1").json()
        assert bess["measurement"] is None and bess["setpoint"]["mode"] == "idle"
        step(client)
        assert client.get("/api/assets/bess/bess1").json()["measurement"]["soc_pct"] == 50
        assert client.get("/api/assets/load/load1").json()["measurement"]["p_kw"] > 0

    def test_points(self, client: TestClient) -> None:
        points = client.get("/api/points").json()
        assert "bess.bess2.soc_pct" in points["names"]
        assert {"bess", "pv", "load", "poi", "site", "meter"} == set(points["point_lists"])
        step(client)
        value = client.get("/api/points/bess.bess1.soc_pct").json()
        assert value == {"name": "bess.bess1.soc_pct", "value": 50, "unit": "%"}
        assert client.get("/api/points/bess.bess1.nope").status_code == 404


class TestMeasurements:
    def test_latest_contains_everything(self, client: TestClient) -> None:
        step(client)
        latest = client.get("/api/measurements/latest").json()
        assert {
            "poi",
            "buses",
            "transformers",
            "bess",
            "pv",
            "loads",
            "step_id",
            "sim_time",
        } <= set(latest)
        assert {bus["name"] for bus in latest["buses"]} >= {"source", "poi", "col:mv1", "lv:bess1"}
        assert len(latest["transformers"]) == 3
        assert latest["poi"]["v_kv"] == pytest.approx(12.47, rel=0.05)

    def test_poi(self, client: TestClient) -> None:
        step(client, 2)
        poi = client.get("/api/measurements/poi").json()
        assert poi["step_id"] == 2 and "p_kw" in poi["poi"]

    def test_history_json_with_fields(self, client: TestClient) -> None:
        step(client, 5)
        body = client.get(
            "/api/measurements/history", params={"fields": "poi.meter.p_kw,bess.bess1.soc_pct"}
        ).json()
        assert body["count"] == 5
        assert body["fields"] == ["poi.meter.p_kw", "bess.bess1.soc_pct"]
        assert [row["step_id"] for row in body["rows"]] == [1, 2, 3, 4, 5]
        assert set(body["rows"][0]) == {
            "sim_time",
            "step_id",
            "poi.meter.p_kw",
            "bess.bess1.soc_pct",
        }

    def test_history_time_filter(self, client: TestClient) -> None:
        step(client, 5)
        body = client.get(
            "/api/measurements/history",
            params={
                "from": "2026-06-21T12:00:02Z",
                "to": "2026-06-21T12:00:04Z",
                "fields": "site.sim.step_id",
            },
        ).json()
        assert [row["step_id"] for row in body["rows"]] == [2, 3, 4]

    def test_history_defaults_to_all_measurement_points(self, client: TestClient) -> None:
        step(client)
        body = client.get("/api/measurements/history").json()
        assert "bess.bess2.limit_flags" in body["fields"]
        assert "bess.bess1.p_setpoint_kw" not in body["fields"]

    def test_history_csv(self, client: TestClient) -> None:
        step(client, 3)
        response = client.get(
            "/api/measurements/history", params={"fields": "poi.meter.p_kw", "format": "csv"}
        )
        assert response.headers["content-type"].startswith("text/csv")
        lines = response.text.strip().splitlines()
        assert lines[0] == "sim_time,step_id,poi.meter.p_kw" and len(lines) == 4

    def test_history_bad_fields(self, client: TestClient) -> None:
        step(client)
        params = {"fields": "poi.meter.nope"}
        assert client.get("/api/measurements/history", params=params).status_code == 404
        params = {"fields": "bess.bess1.p_setpoint_kw"}
        assert client.get("/api/measurements/history", params=params).status_code == 422


class TestConfig:
    def test_get_config_and_schema(self, client: TestClient) -> None:
        assert client.get("/api/config").json()["grid"]["vn_kv"] == 12.47
        assert client.get("/api/config/schema").status_code == 404  # /schemas/site-config


class TestSites:
    def test_list_and_get(self, client: TestClient) -> None:
        body = client.get("/api/sites").json()
        assert body["active"] == TEST_SITE
        categories = {site["name"]: site["category"] for site in body["sites"]}
        assert categories["2bess_1pv"] == "default" and categories[TEST_SITE] == "custom"
        assert len(client.get("/api/sites/2bess_1pv").json()["bess"]) == 2
        assert client.get("/api/sites/nope").status_code == 404

    def test_save_then_activate(self, client: TestClient) -> None:
        step(client, 2)
        raw = site_config_dict(n_bess=3, n_pv=2)
        assert client.put("/api/sites/bigger", json=raw).status_code == 200
        assert len(client.get("/api/config").json()["bess"]) == 2  # not active yet
        response = client.post("/api/sites/bigger/activate")
        assert response.status_code == 200, response.text
        assert client.get("/api/sites").json()["active"] == "bigger"
        assert len(client.get("/api/assets").json()["bess"]) == 3
        assert client.get("/api/sim/status").json()["step_id"] == 0
        assert len(step(client)["bess"]) == 3

    def test_saving_the_active_site_reloads_it(self, client: TestClient) -> None:
        assert (
            client.put(f"/api/sites/{TEST_SITE}", json=site_config_dict(n_bess=1)).status_code
            == 200
        )
        assert len(client.get("/api/assets").json()["bess"]) == 1

    def test_active_site_is_protected_while_running(self, client: TestClient) -> None:
        client.post("/api/sim/start")
        response = client.put(f"/api/sites/{TEST_SITE}", json=site_config_dict())
        assert response.status_code == 409
        assert client.post("/api/sites/2bess_1pv/activate").status_code == 409
        client.post("/api/sim/stop")

    def test_cant_delete_the_active_site(self, client: TestClient) -> None:
        assert client.delete(f"/api/sites/{TEST_SITE}").status_code == 409
        assert client.put("/api/sites/spare", json=site_config_dict()).status_code == 200
        assert client.delete("/api/sites/spare").status_code == 204
        assert "spare" not in site_names(client)

    def test_default_sites_cant_be_deleted_but_can_be_edited(self, client: TestClient) -> None:
        response = client.delete("/api/sites/1bess_1pv")
        assert response.status_code == 409 and "default site" in response.json()["detail"]
        site = client.get("/api/sites/1bess_1pv").json()
        site["simulation"]["seed"] = 7
        assert client.put("/api/sites/1bess_1pv", json=site).status_code == 200
        assert client.get("/api/sites/1bess_1pv").json()["simulation"]["seed"] == 7
        listed = {
            entry["name"]: entry["category"] for entry in client.get("/api/sites").json()["sites"]
        }
        assert listed["1bess_1pv"] == "default"  # saving keeps the category

    def test_invalid_sites_are_rejected(self, client: TestClient) -> None:
        raw = site_config_dict()
        raw["bess"][0]["collector"] = "missing"
        response = client.put("/api/sites/broken", json=raw)
        assert response.status_code == 422 and "unknown collector" in response.text
        raw = site_config_dict()
        raw["loads"][0]["profile"]["scenario"] = "no_such_day"
        response = client.put("/api/sites/broken", json=raw)
        assert response.status_code == 422 and "no_such_day" in response.json()["detail"]
        assert client.put("/api/sites/Bad Name", json=site_config_dict()).status_code == 422
        assert "broken" not in site_names(client)

    def test_edits_survive_a_restart(self, profiles_copy: Path) -> None:
        repository = repository_with_test_site(site_config_dict())  # outlives both apps
        with TestClient(create_app(profiles_copy, repository)) as first:
            first.put("/api/sites/kept", json=site_config_dict(n_bess=3))
            first.post("/api/sites/kept/activate")
        with TestClient(create_app(profiles_copy, repository)) as second:
            assert second.get("/api/sites").json()["active"] == "kept"
            assert len(second.get("/api/config").json()["bess"]) == 3

    def test_a_migrated_database_starts_on_its_default_site(self, profiles_copy: Path) -> None:
        repository = InMemoryConfigRepository.with_default_sites()
        with TestClient(create_app(profiles_copy, repository)) as fresh:
            sites = fresh.get("/api/sites").json()
            assert sites["active"] == sites["stored_active"] == DEFAULT_ACTIVE_SITE
            assert sites["sites"] == DEFAULT_SITE_LIST
            reference = fresh.get("/api/sites/2bess_1pv").json()
            assert [meter["id"] for meter in reference["meters"]] == ["m_bess1", "m_bess2", "m_pv1"]

    def test_active_site_override_runs_once_and_protects_both(
        self, profiles_copy: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Custom sites only: default sites can't be deleted anyway.
        repository = repository_with_test_site(site_config_dict())  # stored active: test_site
        for spare in ("override", "spare"):
            asyncio.run(repository.put_site(spare, SiteConfig.model_validate(site_config_dict())))
        monkeypatch.setattr(settings, "active_site", "override")
        with TestClient(create_app(profiles_copy, repository)) as overridden:
            sites = overridden.get("/api/sites").json()
            assert sites["active"] == "override"
            assert sites["stored_active"] == TEST_SITE  # the database keeps its choice
            for protected in ("override", TEST_SITE):
                response = overridden.delete(f"/api/sites/{protected}")
                assert response.status_code == 409 and "active site" in response.json()["detail"]
            assert overridden.delete("/api/sites/spare").status_code == 204


class TestProfiles:
    LOAD_CSV = "timestamp,p_kw,q_kvar\n2026-06-21T00:00:00Z,500,100\n2026-06-22T00:00:00Z,500,100\n"

    def test_list_and_get(self, client: TestClient) -> None:
        scenarios = client.get("/api/profiles").json()
        assert "high_demand" in scenarios["load"] and "cloudy_dynamic" in scenarios["pv"]
        response = client.get("/api/profiles/load/typical")
        assert response.headers["content-type"].startswith("text/csv")
        assert response.text.startswith("timestamp,p_kw,q_kvar")
        assert client.get("/api/profiles/load/nope").status_code == 404
        assert client.get("/api/profiles/wind/typical").status_code == 422

    def test_put_new_scenario(self, client: TestClient) -> None:
        response = client.put("/api/profiles/load/flat_500", content=self.LOAD_CSV)
        assert response.status_code == 200, response.text
        assert response.json()["reloaded_assets"] == []  # not used by the active site
        assert "flat_500" in client.get("/api/profiles").json()["load"]

    def test_put_scenario_in_use_hot_reloads(self, client: TestClient) -> None:
        headers = {"Content-Type": "text/csv"}
        response = client.put("/api/profiles/load/typical", content=self.LOAD_CSV, headers=headers)
        assert response.json()["reloaded_assets"] == ["load1"]
        assert step(client)["loads"][0]["p_kw"] == pytest.approx(500)

    def test_pv_scenario_keeps_configured_scale(self, client: TestClient) -> None:
        csv_text = "timestamp,p_kw,ghi_wm2\n2026-06-21T00:00:00Z,1234,500\n"
        response = client.put("/api/profiles/pv/clear_sky_high", content=csv_text)
        assert response.json()["reloaded_assets"] == ["pv1"]
        # The test site's availability.scale (0.5) still applies.
        assert step(client)["pv"][0]["p_available_kw"] == pytest.approx(1234 * 0.5)

    def test_rejections(self, client: TestClient) -> None:
        # The active site's PV uses clear_sky_high as ac_kw, so p_kw is required.
        irradiance_only = "timestamp,ghi_wm2\n2026-06-21T00:00:00Z,500\n"
        response = client.put("/api/profiles/pv/clear_sky_high", content=irradiance_only)
        assert response.status_code == 422
        response = client.put("/api/profiles/load/bad", content="timestamp,q_kvar\nx,1\n")
        assert response.status_code == 422
        response = client.put("/api/profiles/load/Bad-Name", content=self.LOAD_CSV)
        assert response.status_code == 422
        assert "bad" not in client.get("/api/profiles").json()["load"]

    def test_delete(self, client: TestClient) -> None:
        client.put("/api/profiles/load/flat_500", content=self.LOAD_CSV)
        assert client.delete("/api/profiles/load/flat_500").status_code == 204
        assert "flat_500" not in client.get("/api/profiles").json()["load"]
        assert client.delete("/api/profiles/load/flat_500").status_code == 404

    def test_delete_refused_while_a_site_uses_it(self, client: TestClient) -> None:
        response = client.delete("/api/profiles/load/high_demand")  # 2bess_1pv
        assert response.status_code == 409 and "2bess_1pv" in response.json()["detail"]
        assert "high_demand" in client.get("/api/profiles").json()["load"]


class TestSchemas:
    def test_list_and_get(self, client: TestClient) -> None:
        assert client.get("/api/schemas").json() == ["site-config"]
        schema = client.get("/api/schemas/site-config").json()
        assert schema["title"] == "SiteConfig" and "bess" in schema["properties"]
        assert client.get("/api/schemas/modbus-map").status_code == 404
