"""HTTP API through FastAPI's TestClient (with the lifespan, so the real engine runs).

Every app gets an in-memory configuration repository (the Postgres one is covered by
tests/integration) seeded with the shipped defaults plus a test site made active, and its own copy
of site_config/ for profile CSVs, so nothing writes the repo."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import DEFAULTS, site_config_dict
from fastapi.testclient import TestClient

from powerflow.app import create_app
from powerflow.core.site_library import seed_defaults
from powerflow.site_config import SiteConfig
from powerflow.storage import InMemoryConfigRepository

TEST_SITE = "test_site"


def repository_with_test_site(raw: dict[str, Any]) -> InMemoryConfigRepository:
    """The defaults, plus raw stored as test_site and made the active site."""
    repository = InMemoryConfigRepository()

    async def fill() -> None:
        await seed_defaults(repository, DEFAULTS)
        await repository.put_site(TEST_SITE, SiteConfig.model_validate(raw))
        await repository.set_active_site(TEST_SITE)

    asyncio.run(fill())
    return repository


@pytest.fixture
def repository() -> InMemoryConfigRepository:
    return repository_with_test_site(site_config_dict(n_bess=2))


@pytest.fixture
def client(site_config_copy: Path, repository: InMemoryConfigRepository) -> Iterator[TestClient]:
    with TestClient(create_app(site_config_copy, repository)) as test_client:
        yield test_client


def step(client: TestClient, count: int = 1) -> dict[str, Any]:
    response = client.post("/api/sim/step", params={"count": count})
    assert response.status_code == 200, response.text
    return response.json()


class TestHealthAndStatus:
    def test_health_and_version(self, client: TestClient) -> None:
        assert client.get("/api/health").json() == {"ok": True, "state": "stopped"}
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

    def test_step_needs_test_mode(self, site_config_copy: Path) -> None:
        raw = site_config_dict()
        raw["simulation"]["test_mode"] = False
        repository = repository_with_test_site(raw)
        with TestClient(create_app(site_config_copy, repository)) as test_client:
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
        schema = client.get("/api/config/schema").json()
        assert schema["title"] == "SiteConfig" and "bess" in schema["properties"]


class TestSites:
    def test_list_and_get(self, client: TestClient) -> None:
        body = client.get("/api/sites").json()
        assert body["active"] == TEST_SITE
        assert {"reference_2bess_1pv", TEST_SITE} <= set(body["sites"])
        assert len(client.get("/api/sites/reference_2bess_1pv").json()["bess"]) == 2
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
        assert client.post("/api/sites/reference_2bess_1pv/activate").status_code == 409
        client.post("/api/sim/stop")

    def test_cant_delete_the_active_site(self, client: TestClient) -> None:
        assert client.delete(f"/api/sites/{TEST_SITE}").status_code == 409
        assert client.delete("/api/sites/small_1bess_1pv").status_code == 204
        assert "small_1bess_1pv" not in client.get("/api/sites").json()["sites"]

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
        assert "broken" not in client.get("/api/sites").json()["sites"]

    def test_edits_survive_a_restart(self, site_config_copy: Path) -> None:
        repository = repository_with_test_site(site_config_dict())  # outlives both apps
        with TestClient(create_app(site_config_copy, repository)) as first:
            first.put("/api/sites/kept", json=site_config_dict(n_bess=3))
            first.post("/api/sites/kept/activate")
            modbus_map = first.get(f"{REFERENCE_MAPS}/bess.bess1").json()
            first.put(f"{REFERENCE_MAPS}/bess.bess1", json={**modbus_map, "unit_id": 42})
        with TestClient(create_app(site_config_copy, repository)) as second:
            assert second.get("/api/sites").json()["active"] == "kept"
            assert len(second.get("/api/config").json()["bess"]) == 3
            assert second.get(f"{REFERENCE_MAPS}/bess.bess1").json()["unit_id"] == 42

    def test_deleting_a_site_deletes_its_maps(
        self, client: TestClient, repository: InMemoryConfigRepository
    ) -> None:
        assert client.delete("/api/sites/small_1bess_1pv").status_code == 204
        assert client.get("/api/sites/small_1bess_1pv/modbus-maps").status_code == 404
        # Recreating the site doesn't bring the old maps back.
        client.put("/api/sites/small_1bess_1pv", json=site_config_dict())
        assert client.get("/api/sites/small_1bess_1pv/modbus-maps").json() == []

    def test_fresh_database_gets_the_defaults(self, site_config_copy: Path) -> None:
        with TestClient(create_app(site_config_copy, InMemoryConfigRepository())) as fresh:
            sites = fresh.get("/api/sites").json()
            assert sites["active"] == DEFAULTS.active_site
            assert sites["sites"] == sorted(site.name for site in DEFAULTS.sites)
            assert len(fresh.get(f"{REFERENCE_MAPS}").json()) == 9  # 6 assets + 3 feeder meters


REFERENCE_MAPS = "/api/sites/reference_2bess_1pv/modbus-maps"


class TestModbusMaps:
    def test_every_asset_of_every_site_has_a_map(self, client: TestClient) -> None:
        for site in ("reference_2bess_1pv", "small_1bess_1pv", "three_bess_two_pv"):
            config = client.get(f"/api/sites/{site}").json()
            expected = {
                *(f"bess.{item['id']}" for item in config["bess"]),
                *(f"pv.{item['id']}" for item in config["pv"]),
                *(f"load.{item['id']}" for item in config["loads"]),
                *(f"meter.{item['id']}" for item in config["meters"]),
                "poi.meter",
                "site.sim",
            }
            maps = client.get(f"/api/sites/{site}/modbus-maps").json()
            assert {item["asset"] for item in maps} == expected
            assert not any(item["orphaned"] for item in maps)
            unit_ids = [item["unit_id"] for item in maps]
            assert len(unit_ids) == len(set(unit_ids))

    def test_get(self, client: TestClient) -> None:
        pv_map = client.get(f"{REFERENCE_MAPS}/pv.pv1").json()
        assert (pv_map["asset"], pv_map["unit_id"]) == ("pv.pv1", 3)  # after bess1, bess2
        assert {entry["register_type"] for entry in pv_map["points"]} == {"holding", "input"}
        assert client.get(f"{REFERENCE_MAPS}/bess.nope").status_code == 404
        assert client.get("/api/sites/nope/modbus-maps").status_code == 404

    def test_put_and_delete(self, client: TestClient) -> None:
        pv_map = client.get(f"{REFERENCE_MAPS}/pv.pv1").json()
        edited = {**pv_map, "unit_id": 50, "port": 1502}
        assert client.put(f"{REFERENCE_MAPS}/pv.pv1", json=edited).status_code == 200
        assert client.get(f"{REFERENCE_MAPS}/pv.pv1").json()["port"] == 1502
        assert client.delete(f"{REFERENCE_MAPS}/pv.pv1").status_code == 204
        assets = {item["asset"] for item in client.get(REFERENCE_MAPS).json()}
        assert "pv.pv1" not in assets
        assert client.put(f"{REFERENCE_MAPS}/pv.pv1", json=edited).status_code == 200  # recreate

    def test_rejections(self, client: TestClient) -> None:
        bess_map = client.get(f"{REFERENCE_MAPS}/bess.bess1").json()
        clash = {**bess_map, "unit_id": 2}  # unit 2 is bess.bess2
        response = client.put(f"{REFERENCE_MAPS}/bess.bess1", json=clash)
        assert response.status_code == 422 and "already" in response.json()["detail"]
        mismatch = client.put(f"{REFERENCE_MAPS}/bess.bess2", json=bess_map)
        assert mismatch.status_code == 422
        no_such_asset = {**bess_map, "asset": "bess.bess9", "unit_id": 9}
        response = client.put(f"{REFERENCE_MAPS}/bess.bess9", json=no_such_asset)
        assert response.status_code == 422 and "no asset" in response.json()["detail"]
        bad_point = {"point": "nope", "register_type": "input", "address": 0, "data_type": "uint16"}
        response = client.put(
            f"{REFERENCE_MAPS}/bess.bess1", json={**bess_map, "points": [bad_point]}
        )
        assert response.status_code == 422 and "point list" in response.json()["detail"]

    def test_map_orphaned_when_the_site_drops_the_asset(self, client: TestClient) -> None:
        site = client.get("/api/sites/reference_2bess_1pv").json()
        site["bess"] = site["bess"][:1]  # drop bess2
        # Its meter must go too: a meter on a missing transformer is rejected.
        assert client.put("/api/sites/reference_2bess_1pv", json=site).status_code == 422
        site["meters"] = [item for item in site["meters"] if item["transformer"] != "bess2"]
        assert client.put("/api/sites/reference_2bess_1pv", json=site).status_code == 200
        orphaned = {item["asset"]: item["orphaned"] for item in client.get(REFERENCE_MAPS).json()}
        assert orphaned["bess.bess2"] is True and orphaned["bess.bess1"] is False
        assert orphaned["meter.m_bess2"] is True and orphaned["meter.m_bess1"] is False


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
        response = client.delete("/api/profiles/load/high_demand")  # reference_2bess_1pv
        assert response.status_code == 409 and "reference_2bess_1pv" in response.json()["detail"]
        assert "high_demand" in client.get("/api/profiles").json()["load"]


class TestSchemas:
    def test_list_and_get(self, client: TestClient) -> None:
        assert client.get("/api/schemas").json() == ["modbus-map", "site-config"]
        schema = client.get("/api/schemas/site-config").json()
        assert schema == client.get("/api/config/schema").json()
        assert client.get("/api/schemas/modbus-map").json()["title"] == "ModbusMap"
        assert client.get("/api/schemas/nope").status_code == 404


class TestDefaults:
    def test_info(self, client: TestClient) -> None:
        info = client.get("/api/defaults").json()
        assert info["active_site"] == "reference_2bess_1pv"
        assert "pv.pv1" in info["sites"]["reference_2bess_1pv"]

    def test_restore_keeps_edits_without_overwrite(self, client: TestClient) -> None:
        site = client.get("/api/sites/small_1bess_1pv").json()
        site["site"]["name"] = "edited"
        client.put("/api/sites/small_1bess_1pv", json=site)
        client.delete(f"{REFERENCE_MAPS}/pv.pv1")
        result = client.post("/api/defaults/restore").json()
        assert "small_1bess_1pv" in result["sites_skipped"]
        assert result["maps_written"] == ["reference_2bess_1pv/pv.pv1"]  # only the missing one
        assert client.get("/api/sites/small_1bess_1pv").json()["site"]["name"] == "edited"

    def test_restore_with_overwrite_replaces_edits(self, client: TestClient) -> None:
        site = client.get("/api/sites/small_1bess_1pv").json()
        site["site"]["name"] = "edited"
        client.put("/api/sites/small_1bess_1pv", json=site)
        result = client.post("/api/defaults/restore", params={"overwrite": "true"}).json()
        assert "small_1bess_1pv" in result["sites_written"]
        assert result["active_site_reloaded"] is False  # the active site is test_site
        assert client.get("/api/sites/small_1bess_1pv").json()["site"]["name"] != "edited"

    def test_restore_with_overwrite_needs_a_stopped_simulation(self, client: TestClient) -> None:
        client.post("/api/sim/start")
        response = client.post("/api/defaults/restore", params={"overwrite": "true"})
        assert response.status_code == 409
        client.post("/api/sim/stop")

    def test_restore_brings_back_a_deleted_default_site(self, client: TestClient) -> None:
        client.delete("/api/sites/three_bess_two_pv")
        result = client.post("/api/defaults/restore").json()
        assert "three_bess_two_pv" in result["sites_written"]
        maps = client.get("/api/sites/three_bess_two_pv/modbus-maps").json()
        assert len(maps) == 8
