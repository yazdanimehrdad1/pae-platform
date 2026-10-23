"""Runtime battery overrides: set a BESS's SOC now, and its round-trip efficiency (100 % on every
activate and reset; null = the site config's), in any run state and under auto dispatch."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import PROFILES, site_config_dict
from fastapi.testclient import TestClient

from powerflow.app import create_app
from powerflow.core.auto_dispatch import AutoDispatchRequest
from powerflow.core.battery import BessBatteryRequest, with_round_trip
from powerflow.core.engine import Engine
from powerflow.core.runtime import SiteRuntime
from powerflow.errors import UnknownAssetError
from powerflow.models import bess as bess_model
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.site_config import SiteConfig
from powerflow.storage import InMemoryConfigRepository

TEST_SITE = "test_site"
CONFIG_ETA = 0.9  # charge and discharge in the test site's config


def make_config() -> SiteConfig:
    config_dict = site_config_dict()
    for bess in config_dict["bess"]:
        bess["battery"].update(
            {
                "soc_min_pct": 10,
                "soc_max_pct": 90,
                "efficiency": {"charge": CONFIG_ETA, "discharge": CONFIG_ETA},
            }
        )
    return SiteConfig.model_validate(config_dict)


def make_engine() -> Engine:
    runtime = SiteRuntime.build(make_config(), PROFILES, PandapowerSolver)
    return Engine(runtime, PandapowerSolver, PROFILES)


def request(**fields: float | None) -> BessBatteryRequest:
    return BessBatteryRequest.model_validate(fields)


class TestEfficiency:
    def test_starts_lossless(self) -> None:
        battery = make_engine().battery("bess1")
        assert battery.round_trip_efficiency_pct == 100
        assert (battery.eta_charge, battery.eta_discharge) == (1, 1)

    def test_a_round_trip_is_split_evenly(self) -> None:
        battery = make_engine().set_battery("bess1", request(round_trip_efficiency_pct=81))
        assert battery.round_trip_efficiency_pct == 81
        assert battery.eta_charge == pytest.approx(0.9)
        assert battery.eta_discharge == pytest.approx(0.9)

    def test_null_returns_to_the_site_config(self) -> None:
        battery = make_engine().set_battery("bess1", request(round_trip_efficiency_pct=None))
        assert battery.round_trip_efficiency_pct is None
        assert (battery.eta_charge, battery.eta_discharge) == (CONFIG_ETA, CONFIG_ETA)

    def test_leaving_it_out_keeps_it(self) -> None:
        engine = make_engine()
        engine.set_battery("bess1", request(round_trip_efficiency_pct=90))
        assert engine.set_battery("bess1", request(soc_pct=30)).round_trip_efficiency_pct == 90

    def test_reset_returns_to_lossless(self) -> None:
        engine = make_engine()
        engine.set_battery("bess1", request(round_trip_efficiency_pct=None))
        asyncio.run(engine.reset())
        assert engine.battery("bess1").eta_charge == 1

    def test_lossless_charge_then_discharge_ends_where_it_started(self) -> None:
        params = with_round_trip(make_engine().runtime.bess["bess1"].params, 100)
        state = bess_model.BessState(soc_pct=50)
        for p_kw in (-1000.0, 1000.0):
            output = bess_model.BessOutput(
                p_kw, 0, p_kw, 0, bess_model.BessFlag.NONE, bess_model.BessStatus.RUNNING, 0
            )
            state = bess_model.integrate(params, state, output, 3600)
        assert state.soc_pct == pytest.approx(50)

    def test_losses_follow_the_efficiency(self) -> None:
        lossless, lossy = make_engine(), make_engine()
        lossy.set_battery("bess1", request(round_trip_efficiency_pct=None))
        for engine in (lossless, lossy):
            engine.set_auto_dispatch(
                AutoDispatchRequest.model_validate(
                    {"enabled": True, "power_pct": 40, "defaults": {"start_direction": "discharge"}}
                )
            )
        # Same AC power out, so the lossy one draws more from its cells.
        assert (
            asyncio.run(lossy.step(5)).bess[0].soc_pct
            < asyncio.run(lossless.step(5)).bess[0].soc_pct
        )


class TestSoc:
    def test_sets_the_soc_now(self) -> None:
        engine = make_engine()
        assert engine.set_battery("bess1", request(soc_pct=30)).soc_pct == 30
        assert asyncio.run(engine.step(1)).bess[0].soc_pct == pytest.approx(30, abs=0.1)

    def test_clamps_to_the_battery_band(self) -> None:
        engine = make_engine()
        assert engine.set_battery("bess1", request(soc_pct=2)).soc_pct == 10
        assert engine.set_battery("bess1", request(soc_pct=99)).soc_pct == 90

    def test_works_while_auto_dispatch_drives_it(self) -> None:
        engine = make_engine()
        engine.set_auto_dispatch(AutoDispatchRequest(enabled=True))
        assert engine.set_battery("bess1", request(soc_pct=20)).soc_pct == 20

    def test_unknown_bess(self) -> None:
        with pytest.raises(UnknownAssetError):
            make_engine().set_battery("nope", request(soc_pct=20))


@pytest.fixture
def client(profiles_copy: Path) -> Iterator[TestClient]:
    repository = InMemoryConfigRepository.with_default_sites()

    async def fill() -> None:
        await repository.put_site(TEST_SITE, make_config())
        await repository.set_active_site(TEST_SITE)

    asyncio.run(fill())
    with TestClient(create_app(profiles_copy, repository)) as test_client:
        yield test_client


URL = "/api/assets/bess/bess1/battery"


class TestApi:
    def test_put_and_get(self, client: TestClient) -> None:
        response = client.put(URL, json={"soc_pct": 25, "round_trip_efficiency_pct": 90})
        assert response.status_code == 200, response.text
        assert response.json()["soc_pct"] == 25
        battery = client.get("/api/assets/bess/bess1").json()["battery"]
        assert (battery["soc_pct"], battery["round_trip_efficiency_pct"]) == (25, 90)

    def test_null_efficiency_is_the_site_config(self, client: TestClient) -> None:
        battery = client.put(URL, json={"round_trip_efficiency_pct": None}).json()
        assert battery["round_trip_efficiency_pct"] is None
        assert battery["eta_charge"] == CONFIG_ETA

    @pytest.mark.parametrize(
        "body",
        [
            {"soc_pct": -1},
            {"soc_pct": 101},
            {"round_trip_efficiency_pct": 40},
            {"round_trip_efficiency_pct": 101},
            {"surprise": 1},
        ],
    )
    def test_invalid_is_422(self, client: TestClient, body: dict[str, float]) -> None:
        assert client.put(URL, json=body).status_code == 422

    def test_unknown_bess_is_404(self, client: TestClient) -> None:
        assert client.put("/api/assets/bess/nope/battery", json={}).status_code == 404
