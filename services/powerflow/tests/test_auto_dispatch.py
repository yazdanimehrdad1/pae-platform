"""Auto dispatch: each included BESS cycles inside its own SOC window on its own, at a share of its
rating, turning only at an edge (after an optional rest), with optional power noise, an extra
ramp limit, a start direction and a fixed Q. Settings are site-wide defaults with per-BESS
overrides. Setpoint writes to a driven BESS are rejected while an excluded one takes them, an
alarm reset still goes, leaving auto dispatch leaves a BESS idle, and a reset turns it off."""

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from conftest import PROFILES, site_config_dict
from fastapi.testclient import TestClient

from powerflow.app import create_app
from powerflow.core.auto_dispatch import AutoDispatchBessSettings, AutoDispatchRequest, resolve
from powerflow.core.engine import Engine
from powerflow.core.runtime import SiteRuntime
from powerflow.core.setpoints import BessSetpointRequest, BessSetpointState, SetpointService
from powerflow.errors import AutoDispatchError, InvalidStateError, UnknownAssetError
from powerflow.models.auto_dispatch import (
    AutoDispatchBessState,
    AutoDispatchDirection,
    AutoDispatchPhase,
    AutoDispatchSettings,
    advance,
    initial_state,
)
from powerflow.models.bess import BessMode, BessParams, BessSetpoint
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.site_config import Priority, SiteConfig
from powerflow.storage import InMemoryConfigRepository

CHARGE = AutoDispatchDirection.CHARGE
DISCHARGE = AutoDispatchDirection.DISCHARGE

PARAMS = BessParams(
    p_discharge_max_kw=2500,
    p_charge_max_kw=2000,
    s_rated_kva=2750,
    capacity_kwh=10000,
    soc_min_pct=10,
    soc_max_pct=90,
    eta_charge=0.95,
    eta_discharge=0.9,
    ramp_kw_per_s=None,
    priority=Priority.P,
    aux_load_kw=0,
)
WINDOW = AutoDispatchSettings(soc_low_pct=20, soc_high_pct=80, discharge_pct=100, charge_pct=100)

TEST_SITE = "test_site"
QUARTER_HOUR_S = 900.0


def step(
    settings: AutoDispatchSettings,
    state: AutoDispatchBessState,
    soc_pct: float = 50,
    t_s: float = 0,
    dt_s: float = 1,
    power_pct: float | None = None,
    noise_draw: float = 0,
) -> tuple[AutoDispatchBessState, BessSetpoint]:
    """power_pct: both directions at that % (else the settings')."""
    if power_pct is not None:
        settings = replace(settings, discharge_pct=power_pct, charge_pct=power_pct)
    return advance(PARAMS, settings, state, soc_pct, t_s, dt_s, noise_draw)


class TestDirection:
    def test_starts_discharging_above_the_middle_of_the_window(self) -> None:
        assert initial_state(WINDOW, 50.1).direction is DISCHARGE
        assert initial_state(WINDOW, 50.0).direction is CHARGE

    def test_a_start_direction_wins(self) -> None:
        settings = replace(WINDOW, start_direction=CHARGE)
        assert initial_state(settings, 75).direction is CHARGE

    def test_turns_at_the_window_edges_not_the_batterys(self) -> None:
        state, _ = step(WINDOW, AutoDispatchBessState(DISCHARGE), soc_pct=20)
        assert state.direction is CHARGE
        state, _ = step(WINDOW, AutoDispatchBessState(CHARGE), soc_pct=80)
        assert state.direction is DISCHARGE
        state, _ = step(WINDOW, AutoDispatchBessState(DISCHARGE), soc_pct=30)
        assert state.direction is DISCHARGE  # inside the window: keeps going


class TestPower:
    def test_a_share_of_the_rating_in_each_direction(self) -> None:
        _, setpoint = step(WINDOW, AutoDispatchBessState(DISCHARGE), power_pct=50)
        assert setpoint == BessSetpoint(1250, 0, BessMode.PQ)
        _, setpoint = step(WINDOW, AutoDispatchBessState(CHARGE), power_pct=25)
        assert setpoint == BessSetpoint(-500, 0, BessMode.PQ)

    def test_discharge_and_charge_shares_apply_by_direction(self) -> None:
        split = replace(WINDOW, discharge_pct=80, charge_pct=30)
        _, setpoint = step(split, AutoDispatchBessState(DISCHARGE))
        assert setpoint.p_kw == pytest.approx(2000)  # 80 % of 2500
        _, setpoint = step(split, AutoDispatchBessState(CHARGE))
        assert setpoint.p_kw == pytest.approx(-600)  # 30 % of 2000

    def test_noise_scales_the_target_and_never_passes_the_rating(self) -> None:
        noisy = replace(WINDOW, p_noise_std_pct=10)
        _, setpoint = step(noisy, AutoDispatchBessState(DISCHARGE), power_pct=50, noise_draw=1)
        assert setpoint.p_kw == pytest.approx(1375)  # 1250 × (1 + 1 × 10 %)
        _, setpoint = step(noisy, AutoDispatchBessState(DISCHARGE), power_pct=100, noise_draw=3)
        assert setpoint.p_kw == pytest.approx(2500)
        _, setpoint = step(WINDOW, AutoDispatchBessState(DISCHARGE), power_pct=50, noise_draw=3)
        assert setpoint.p_kw == pytest.approx(1250)  # std 0: no noise

    def test_the_ramp_limits_the_change_per_step(self) -> None:
        ramped = replace(WINDOW, ramp_kw_per_s=10)
        state, setpoint = step(ramped, AutoDispatchBessState(DISCHARGE), dt_s=5)
        assert setpoint.p_kw == pytest.approx(50) and state.p_cmd_kw == pytest.approx(50)
        _, setpoint = step(ramped, state, dt_s=5)
        assert setpoint.p_kw == pytest.approx(100)

    def test_the_last_step_lands_on_the_window_edge(self) -> None:
        # 0.5 % above the low edge: 50 kWh × η_d 0.9 = 45 kWh in one 15 min step = 180 kW.
        _, setpoint = step(WINDOW, AutoDispatchBessState(DISCHARGE), soc_pct=20.5, dt_s=900)
        assert setpoint.p_kw == pytest.approx(180)

    def test_q_is_held(self) -> None:
        _, setpoint = step(replace(WINDOW, q_kvar=-300), AutoDispatchBessState(CHARGE))
        assert setpoint.q_kvar == -300


class TestRest:
    def test_rests_at_an_edge_then_turns(self) -> None:
        resting = replace(WINDOW, rest_s=60)
        state, setpoint = step(resting, AutoDispatchBessState(DISCHARGE), soc_pct=20, t_s=100)
        assert state.phase is AutoDispatchPhase.RESTING and setpoint.p_kw == 0
        state, setpoint = step(resting, state, soc_pct=20, t_s=159)
        assert state.phase is AutoDispatchPhase.RESTING and setpoint.p_kw == 0
        state, setpoint = step(resting, state, soc_pct=20, t_s=160)
        assert state.phase is AutoDispatchPhase.CHARGING and setpoint.p_kw < 0


class TestResolve:
    def test_override_then_defaults_then_the_battery(self) -> None:
        defaults = AutoDispatchBessSettings(soc_low_pct=30, rest_s=60, q_kvar=100)
        override = AutoDispatchBessSettings(soc_high_pct=70, rest_s=0)
        settings = resolve("bess1", PARAMS, defaults, override)
        assert settings == AutoDispatchSettings(
            soc_low_pct=30,
            soc_high_pct=70,
            discharge_pct=50,
            charge_pct=50,
            rest_s=0,
            q_kvar=100,
        )
        assert resolve("bess1", PARAMS, AutoDispatchBessSettings(), None) == AutoDispatchSettings(
            soc_low_pct=10, soc_high_pct=90, discharge_pct=50, charge_pct=50
        )

    def test_power_shares_override_then_defaults_then_the_request(self) -> None:
        defaults = AutoDispatchBessSettings(charge_pct=40)
        override = AutoDispatchBessSettings(discharge_pct=90)
        settings = resolve("bess1", PARAMS, defaults, override, power_pct=20)
        assert settings is not None
        assert (settings.discharge_pct, settings.charge_pct) == (90, 40)
        settings = resolve("bess1", PARAMS, AutoDispatchBessSettings(), None, power_pct=20)
        assert settings is not None
        assert (settings.discharge_pct, settings.charge_pct) == (20, 20)

    def test_excluded_is_none(self) -> None:
        defaults = AutoDispatchBessSettings(included=False)
        assert resolve("bess1", PARAMS, defaults, None) is None
        included = AutoDispatchBessSettings(included=True)
        assert resolve("bess1", PARAMS, defaults, included) is not None

    def test_the_window_must_fit_the_battery_and_not_be_empty(self) -> None:
        with pytest.raises(AutoDispatchError):
            resolve("bess1", PARAMS, AutoDispatchBessSettings(soc_low_pct=5), None)
        with pytest.raises(AutoDispatchError):  # default low 60, override high 50
            resolve(
                "bess1",
                PARAMS,
                AutoDispatchBessSettings(soc_low_pct=60),
                AutoDispatchBessSettings(soc_high_pct=50),
            )


def make_engine(n_bess: int = 1, soc_initial_pct: float = 60) -> Engine:
    config_dict = site_config_dict(n_bess=n_bess)
    config_dict["simulation"]["step_s"] = QUARTER_HOUR_S
    for bess in config_dict["bess"]:
        bess["battery"].update(
            {"soc_min_pct": 10, "soc_max_pct": 90, "soc_initial_pct": soc_initial_pct}
        )
    config = SiteConfig.model_validate(config_dict)
    return Engine(SiteRuntime.build(config, PROFILES, PandapowerSolver), PandapowerSolver, PROFILES)


def on(power_pct: float = 100, **request: Any) -> AutoDispatchRequest:
    return AutoDispatchRequest.model_validate({"enabled": True, "power_pct": power_pct, **request})


def socs(engine: Engine, steps: int) -> list[list[float]]:
    """Per step, every BESS's SOC."""
    return [[bess.soc_pct for bess in asyncio.run(engine.step(1)).bess] for _ in range(steps)]


class TestEngine:
    def test_cycles_down_to_the_low_edge_then_up_to_the_high_edge(self) -> None:
        engine = make_engine(soc_initial_pct=60)
        engine.set_auto_dispatch(on(defaults={"soc_low_pct": 20, "soc_high_pct": 80}))
        trace = [row[0] for row in socs(engine, 30)]
        assert all(20 <= soc <= 80 for soc in trace)
        first_low = next(index for index, soc in enumerate(trace) if soc == pytest.approx(20))
        first_high = next(index for index, soc in enumerate(trace) if soc == pytest.approx(80))
        assert first_low < first_high

    def test_each_bess_keeps_to_its_own_window(self) -> None:
        engine = make_engine(n_bess=2, soc_initial_pct=50)
        request = on(
            defaults={"soc_low_pct": 20, "soc_high_pct": 80},
            bess={"bess2": {"soc_low_pct": 40, "soc_high_pct": 60}},
        )
        engine.set_auto_dispatch(request)
        trace = socs(engine, 30)
        assert all(20 <= first <= 80 and 40 <= second <= 60 for first, second in trace)
        assert min(second for _, second in trace) == pytest.approx(40)
        assert min(first for first, _ in trace) == pytest.approx(20)

    def test_each_bess_drives_at_its_own_share(self) -> None:
        engine = make_engine(n_bess=2, soc_initial_pct=60)
        request = on(
            power_pct=50,
            defaults={"start_direction": "discharge"},
            bess={"bess1": {"discharge_pct": 80}, "bess2": {"discharge_pct": 30}},
        )
        report = engine.set_auto_dispatch(request)
        assert [(row.discharge_pct, row.charge_pct) for row in report.bess] == [(80, 50), (30, 50)]
        bess = asyncio.run(engine.step(1)).bess
        rating = engine.runtime.bess["bess1"].params.p_discharge_max_kw
        assert [item.p_kw for item in bess] == pytest.approx([rating * 0.8, rating * 0.3])

    def test_rests_between_cycles(self) -> None:
        engine = make_engine(soc_initial_pct=21)
        request = on(defaults={"soc_low_pct": 20, "rest_s": 1800, "start_direction": "discharge"})
        engine.set_auto_dispatch(request)
        asyncio.run(engine.step(2))  # lands on 20 %, then sees the edge and starts resting
        assert engine.auto_dispatch_status().bess[0].phase is AutoDispatchPhase.RESTING
        assert engine.setpoints.bess("bess1").p_kw == 0
        asyncio.run(engine.step(2))  # 30 min later the rest is over
        assert engine.auto_dispatch_status().bess[0].phase is AutoDispatchPhase.CHARGING

    def test_an_excluded_bess_takes_setpoints_and_a_driven_one_refuses_them(self) -> None:
        engine = make_engine(n_bess=2)
        service = SetpointService(engine)
        engine.set_auto_dispatch(on(bess={"bess2": {"included": False}}))
        with pytest.raises(InvalidStateError):
            service.write_bess("bess1", BessSetpointRequest(p_kw=100))
        service.write_bess("bess1", BessSetpointRequest(alarm_reset=True))  # still allowed
        accepted = service.write_bess("bess2", BessSetpointRequest(p_kw=100)).accepted
        assert isinstance(accepted, BessSetpointState) and accepted.p_kw == 100
        asyncio.run(engine.step(1))
        assert engine.setpoints.bess("bess2").p_kw == 100  # auto dispatch left it alone
        report = engine.auto_dispatch_status()
        assert [(row.asset_id, row.included) for row in report.bess] == [
            ("bess1", True),
            ("bess2", False),
        ]

    def test_excluding_a_bess_later_leaves_it_idle(self) -> None:
        engine = make_engine(n_bess=2)
        engine.set_auto_dispatch(on())
        asyncio.run(engine.step(1))
        engine.set_auto_dispatch(on(bess={"bess2": {"included": False}}))
        assert engine.setpoints.bess("bess2") == BessSetpoint()

    def test_changing_settings_keeps_the_direction(self) -> None:
        engine = make_engine(soc_initial_pct=60)
        engine.set_auto_dispatch(on())
        asyncio.run(engine.step(2))
        report = engine.set_auto_dispatch(on(power_pct=20, defaults={"q_kvar": 50}))
        assert report.power_pct == 20 and report.bess[0].direction is DISCHARGE

    def test_noise_is_the_same_for_the_same_seed(self) -> None:
        runs: list[list[float]] = []
        for _ in range(2):
            engine = make_engine()
            engine.set_auto_dispatch(on(power_pct=50, defaults={"p_noise_std_pct": 10}))
            runs.append([asyncio.run(engine.step(1)).bess[0].p_kw for _ in range(3)])
        assert runs[0] == runs[1]
        assert len(set(runs[0])) > 1  # and it does vary

    def test_turning_it_off_and_reset_leave_the_bess_idle(self) -> None:
        engine = make_engine()
        engine.set_auto_dispatch(on())
        asyncio.run(engine.step(2))
        report = engine.set_auto_dispatch(AutoDispatchRequest(enabled=False))
        assert not report.enabled and report.bess == []
        assert engine.setpoints.bess("bess1") == BessSetpoint()
        engine.set_auto_dispatch(on())
        asyncio.run(engine.reset())
        assert not engine.auto_dispatch_enabled

    def test_an_override_of_no_bess_is_unknown(self) -> None:
        with pytest.raises(UnknownAssetError):
            make_engine().set_auto_dispatch(on(bess={"nope": {}}))


@pytest.fixture
def client(profiles_copy: Path) -> Iterator[TestClient]:
    repository = InMemoryConfigRepository.with_default_sites()

    async def fill() -> None:
        await repository.put_site(TEST_SITE, SiteConfig.model_validate(site_config_dict()))
        await repository.set_active_site(TEST_SITE)

    asyncio.run(fill())
    with TestClient(create_app(profiles_copy, repository)) as test_client:
        yield test_client


URL = "/api/sim/auto-dispatch"


class TestApi:
    def test_round_trip_echoes_the_settings(self, client: TestClient) -> None:
        off = client.get(URL).json()
        assert off["enabled"] is False and off["bess"] == [] and off["bess_overrides"] == {}
        body = {
            "enabled": True,
            "power_pct": 50,
            "defaults": {"soc_low_pct": 20, "rest_s": 60},
            "bess": {"bess1": {"soc_high_pct": 70, "q_kvar": 100}},
        }
        response = client.put(URL, json=body)
        assert response.status_code == 200, response.text
        report = response.json()
        assert report["defaults"] == {
            **dict.fromkeys(AutoDispatchBessSettings.model_fields),
            **body["defaults"],
        }
        assert report["bess_overrides"]["bess1"]["soc_high_pct"] == 70
        row = report["bess"][0]
        assert (row["included"], row["soc_low_pct"], row["soc_high_pct"], row["q_kvar"]) == (
            True,
            20,
            70,
            100,
        )
        assert row["phase"] == "discharging"  # SOC 50 % is above the middle of 20–70 %
        bess = client.post("/api/sim/step").json()["bess"][0]
        assert bess["p_kw"] == pytest.approx(1250)

    @pytest.mark.parametrize(
        "body",
        [
            {"enabled": True, "power_pct": 0},
            {"enabled": True, "power_pct": 101},
            {"enabled": True, "defaults": {"soc_low_pct": 60, "soc_high_pct": 40}},
            {"enabled": True, "defaults": {"soc_low_pct": 1}},  # below the battery's 5 %
            {"enabled": True, "defaults": {"p_noise_std_pct": 80}},
            {"enabled": True, "defaults": {"surprise": 1}},
        ],
    )
    def test_invalid_settings_are_422(self, client: TestClient, body: dict[str, Any]) -> None:
        assert client.put(URL, json=body).status_code == 422

    def test_an_override_of_no_bess_is_404(self, client: TestClient) -> None:
        assert client.put(URL, json={"enabled": True, "bess": {"nope": {}}}).status_code == 404

    def test_setpoint_writes_are_409_while_driven(self, client: TestClient) -> None:
        client.put(URL, json={"enabled": True})
        setpoint = "/api/assets/bess/bess1/setpoint"
        assert client.put(setpoint, json={"p_kw": 100}).status_code == 409
        assert client.put(setpoint, json={"alarm_reset": True}).status_code == 200
        client.put(URL, json={"enabled": True, "bess": {"bess1": {"included": False}}})
        assert client.put(setpoint, json={"p_kw": 100}).status_code == 200
