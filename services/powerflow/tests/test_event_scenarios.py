"""Event scenarios: scheduling (step and sim-time triggers, missed events, skipped ticks), the
engine playing one deterministically, and the HTTP API (per-site CRUD, start/stop)."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from conftest import POINT_STANDARD, PROFILES, default_site, make_site_config, site_config_dict
from fastapi.testclient import TestClient

from powerflow.app import create_app
from powerflow.conditions import (
    AlarmResetChange,
    AssetFaultChange,
    BreakerChange,
    GridVoltageChange,
)
from powerflow.conditions.builtin_scenarios import BUILTIN_SCENARIOS
from powerflow.conditions.scenario import (
    EventScenario,
    ExpectedPoint,
    ScenarioEvent,
    StepTrigger,
    TimeTrigger,
    due,
    first_step_at,
    schedule,
    validate_scenario,
)
from powerflow.core.engine import Engine
from powerflow.core.point_registry import PointRegistry
from powerflow.core.runtime import SiteRuntime
from powerflow.core.setpoints import SetpointService
from powerflow.errors import ConditionError, InvalidStateError, NotFoundError
from powerflow.models.bess import BessStatus
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.point_standard import build_layout
from powerflow.point_standard.expectations import expectation_problems, failures_at
from powerflow.point_standard.sources import sources_from
from powerflow.site_config import SiteConfig
from powerflow.storage import InMemoryConfigRepository
from powerflow.storage.seed_data import default_sites

ORIGIN = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)


def open_at(step: int, breaker: str = "bess1") -> ScenarioEvent:
    return ScenarioEvent(
        at=StepTrigger(step=step), change=BreakerChange(breaker=breaker, closed=False)
    )


class TestSchedule:
    def test_step_triggers_count_from_the_start(self) -> None:
        run = schedule("s", EventScenario(events=[open_at(3), open_at(1)]), 10, ORIGIN, 1.0)
        assert [event.step for event in run.pending] == [11, 13]

    def test_time_triggers_and_missed_events(self) -> None:
        events = [
            ScenarioEvent(
                at=TimeTrigger(sim_time=ORIGIN + timedelta(seconds=20.5)),
                change=GridVoltageChange(vm_pu=0.9),
            ),
            ScenarioEvent(
                at=TimeTrigger(sim_time=ORIGIN + timedelta(seconds=5)),
                change=GridVoltageChange(vm_pu=None),
            ),
        ]
        run = schedule("s", EventScenario(events=events), 10, ORIGIN, 1.0)
        assert [event.step for event in run.pending] == [21]  # the first step at/after 20.5 s
        assert run.missed == 1 and run.total == 2

    def test_first_step_at(self) -> None:
        assert first_step_at(ORIGIN + timedelta(seconds=10), ORIGIN, 1.0) == 10
        assert first_step_at(ORIGIN + timedelta(seconds=10.2), ORIGIN, 5.0) == 3

    def test_due_takes_everything_up_to_the_step_in_order(self) -> None:
        scenario = EventScenario(events=[open_at(2, "pv1"), open_at(1), open_at(2, "load1")])
        run = schedule("s", scenario, 0, ORIGIN, 1.0)
        changes, run = due(run, 1)
        assert [change.breaker for change in changes] == ["bess1"]  # type: ignore[union-attr]
        changes, run = due(run, 5)  # skipped ticks: the whole gap, in list order
        assert [change.breaker for change in changes] == ["pv1", "load1"]  # type: ignore[union-attr]
        assert run.fired == 3 and not run.pending

    def test_validation_names_each_bad_event(self) -> None:
        scenario = EventScenario(events=[open_at(1), open_at(2, "nope"), open_at(3, "poi")])
        problems = validate_scenario(scenario, make_site_config())
        assert len(problems) == 1 and problems[0].startswith("event 2:")

    def test_an_empty_scenario_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            EventScenario(events=[])


def make_engine() -> Engine:
    config = SiteConfig.model_validate(site_config_dict())
    return Engine(SiteRuntime.build(config, PROFILES, PandapowerSolver), PandapowerSolver, PROFILES)


class TestEnginePlayer:
    def test_events_fire_before_their_step(self) -> None:
        engine = make_engine()
        asyncio.run(engine.step(5))
        scenario = EventScenario(
            events=[
                ScenarioEvent(at=StepTrigger(step=2), change=AssetFaultChange(asset_id="bess1")),
                ScenarioEvent(
                    at=StepTrigger(step=4),
                    change=AssetFaultChange(asset_id="bess1", active=False),
                ),
                ScenarioEvent(at=StepTrigger(step=5), change=AlarmResetChange(asset_id="bess1")),
            ]
        )
        report = asyncio.run(engine.start_scenario("trip", scenario))
        assert report.scenario is not None and report.scenario.next_step == 7
        statuses = [asyncio.run(engine.step(1)).bess[0].status for _ in range(5)]
        assert statuses == [
            BessStatus.IDLE,
            BessStatus.FAULT,  # step 7
            BessStatus.FAULT,
            BessStatus.FAULT,  # step 9: cleared, but latched
            BessStatus.IDLE,  # step 10: alarm reset
        ]
        finished = engine.active_conditions().scenario
        assert finished is not None and finished.finished and finished.fired == 3
        assert engine.status().scenario == "trip"

    def test_scenarios_overlap_and_stop_one_or_all(self) -> None:
        engine = make_engine()
        asyncio.run(engine.start_scenario("a", EventScenario(events=[open_at(1), open_at(9)])))
        asyncio.run(engine.start_scenario("b", EventScenario(events=[open_at(1, "pv1")])))
        with pytest.raises(InvalidStateError):  # the same scenario can't be queued twice
            asyncio.run(engine.start_scenario("a", EventScenario(events=[open_at(1)])))
        asyncio.run(engine.step(1))
        report = engine.active_conditions()
        assert [run.name for run in report.scenarios] == ["a", "b"]
        assert report.scenario is not None and report.scenario.name == "b"  # the latest
        closed = {item.id: item.closed for item in report.breakers}
        assert not closed["bess1"] and not closed["pv1"]  # both played
        report = asyncio.run(engine.stop_scenario("a"))
        assert [run.name for run in report.scenarios] == ["b"]
        with pytest.raises(NotFoundError):
            asyncio.run(engine.stop_scenario("a"))
        report = asyncio.run(engine.stop_scenario())
        assert report.scenarios == [] and report.scenario is None
        assert not next(item for item in report.breakers if item.id == "bess1").closed  # stays

    def test_overlapping_changes_fire_in_step_then_start_order(self) -> None:
        engine = make_engine()
        close = ScenarioEvent(
            at=StepTrigger(step=2), change=BreakerChange(breaker="bess1", closed=True)
        )
        asyncio.run(engine.start_scenario("opens", EventScenario(events=[open_at(2)])))
        asyncio.run(engine.start_scenario("closes", EventScenario(events=[close])))
        asyncio.run(engine.step(2))
        breakers = {item.id: item.closed for item in engine.active_conditions().breakers}
        assert breakers["bess1"]  # same step: the later-started scenario wins

    def test_scheduled_start_and_the_current_scenario_step(self) -> None:
        engine = make_engine()
        asyncio.run(engine.step(3))
        current = engine.status().step_id
        with pytest.raises(ConditionError):
            asyncio.run(engine.start_scenario("late", EventScenario(events=[open_at(1)]), current))
        scenario = EventScenario(events=[open_at(1), open_at(4, "pv1")])
        report = asyncio.run(engine.start_scenario("later", scenario, at_step=current + 3))
        (run,) = report.scenarios
        assert (run.state, run.current_step, run.start_step, run.length) == (
            "scheduled",
            None,
            current + 3,
            4,
        )
        asyncio.run(engine.step(2))  # current + 2: still ahead
        assert next(
            item for item in engine.active_conditions().breakers if item.id == "bess1"
        ).closed
        asyncio.run(engine.step(1))  # current + 3 = its step 1
        report = engine.active_conditions()
        assert (report.scenarios[0].state, report.scenarios[0].current_step) == ("playing", 1)
        assert not next(item for item in report.breakers if item.id == "bess1").closed
        asyncio.run(engine.step(3))  # its step 4: the last event
        run = engine.active_conditions().scenarios[0]
        assert (run.state, run.current_step, run.fired) == ("finished", 4, 2)
        # a finished run of the same scenario gives way to a new one
        now = engine.status().step_id
        (rerun,) = asyncio.run(engine.start_scenario("later", scenario)).scenarios
        assert (rerun.state, rerun.start_step, rerun.fired) == ("scheduled", now + 1, 0)

    def test_invalid_scenario_is_refused(self) -> None:
        engine = make_engine()
        with pytest.raises(ConditionError):
            asyncio.run(engine.start_scenario("x", EventScenario(events=[open_at(1, "nope")])))

    def test_clear_and_reset_stop_it(self) -> None:
        engine = make_engine()
        asyncio.run(engine.start_scenario("a", EventScenario(events=[open_at(5)])))
        assert engine.clear_conditions().scenario is None
        asyncio.run(engine.start_scenario("a", EventScenario(events=[open_at(5)])))
        asyncio.run(engine.reset())
        assert engine.active_conditions().scenario is None


TEST_SITE = "test_site"
SCENARIO_BODY: dict[str, Any] = {
    "description": "Trip BESS 1, then restore it",
    "events": [
        {
            "at": {"kind": "step", "step": 1},
            "change": {"type": "asset_fault", "asset_id": "bess1"},
            "label": "trip",
        },
        {
            "at": {"kind": "step", "step": 3},
            "change": {"type": "asset_fault", "asset_id": "bess1", "active": False},
        },
    ],
}


@pytest.fixture
def client(profiles_copy: Path) -> Iterator[TestClient]:
    repository = InMemoryConfigRepository.with_default_sites()

    async def fill() -> None:
        await repository.put_site(TEST_SITE, make_site_config())
        await repository.set_active_site(TEST_SITE)

    asyncio.run(fill())
    with TestClient(create_app(profiles_copy, repository)) as test_client:
        yield test_client


class TestApi:
    def test_conditions_round_trip(self, client: TestClient) -> None:
        response = client.post(
            "/api/sim/conditions", json={"type": "breaker", "breaker": "bess1", "closed": False}
        )
        assert response.status_code == 200, response.text
        assert not next(item for item in response.json()["breakers"] if item["id"] == "bess1")[
            "closed"
        ]
        bess = client.post("/api/sim/step").json()["bess"][0]
        assert bess["breaker_state_name"] == "OPEN"
        missing = {"type": "asset_fault", "asset_id": "nope"}
        assert client.post("/api/sim/conditions", json=missing).status_code == 404
        on_load = {"type": "asset_fault", "asset_id": "load1"}
        assert client.post("/api/sim/conditions", json=on_load).status_code == 422
        cleared = client.post("/api/sim/conditions/clear").json()
        assert all(item["closed"] for item in cleared["breakers"])

    def test_scenario_crud_and_play(self, client: TestClient) -> None:
        base = f"/api/sites/{TEST_SITE}/event-scenarios"
        assert client.put(f"{base}/trip", json=SCENARIO_BODY).status_code == 200
        listed = client.get(base).json()
        assert listed == [
            {
                "name": "trip",
                "category": "custom",
                "description": "Trip BESS 1, then restore it",
                "event_count": 2,
                "expected_points": [],
                "valid": True,
                "problems": [],
            }
        ]
        assert client.get(f"{base}/trip").json()["events"][0]["label"] == "trip"
        started = client.post("/api/sim/event-scenario/start", json={"name": "trip"})
        assert started.status_code == 200 and started.json()["scenario"]["name"] == "trip"
        conflict = client.post("/api/sim/event-scenario/start", json={"name": "trip"})
        assert conflict.status_code == 409
        assert client.post("/api/sim/step").json()["bess"][0]["status_name"] == "FAULT"
        assert client.post("/api/sim/event-scenario/stop").json()["scenario"] is None
        assert client.delete(f"{base}/trip").status_code == 204
        assert client.get(f"{base}/trip").status_code == 404

    def test_schedule_at_a_step_and_stop_one_run(self, client: TestClient) -> None:
        base = f"/api/sites/{TEST_SITE}/event-scenarios"
        assert client.put(f"{base}/trip", json=SCENARIO_BODY).status_code == 200
        client.post("/api/sim/stop")
        step = client.get("/api/sim/status").json()["step_id"]
        late = client.post("/api/sim/event-scenario/start", json={"name": "trip", "at_step": step})
        assert late.status_code == 422
        started = client.post(
            "/api/sim/event-scenario/start", json={"name": "trip", "at_step": step + 50}
        ).json()
        (run,) = started["scenarios"]
        assert (run["state"], run["start_step"], run["current_step"]) == (
            "scheduled",
            step + 50,
            None,
        )
        stopped = client.post("/api/sim/event-scenario/stop", json={"name": "trip"}).json()
        assert stopped["scenarios"] == []
        missing = client.post("/api/sim/event-scenario/stop", json={"name": "trip"})
        assert missing.status_code == 404
        assert client.post("/api/sim/event-scenario/stop").status_code == 200  # no body: all

    def test_scenarios_are_checked_against_their_site(self, client: TestClient) -> None:
        bad = {
            "events": [
                {
                    "at": {"kind": "step", "step": 1},
                    "change": {"type": "breaker", "breaker": "bess9", "closed": False},
                }
            ]
        }
        response = client.put(f"/api/sites/{TEST_SITE}/event-scenarios/bad", json=bad)
        assert response.status_code == 422 and "bess9" in response.json()["detail"]
        assert client.get("/api/sites/nope/event-scenarios").status_code == 404
        unknown = client.post("/api/sim/event-scenario/start", json={"name": "none"})
        assert unknown.status_code == 404

    def test_a_site_edit_can_make_a_scenario_stale(self, client: TestClient) -> None:
        base = f"/api/sites/{TEST_SITE}/event-scenarios"
        client.put(f"{base}/trip", json=SCENARIO_BODY)
        client.post("/api/sim/stop")
        raw = site_config_dict()
        raw["bess"][0]["id"] = "bess_renamed"
        assert client.put(f"/api/sites/{TEST_SITE}", json=raw).status_code == 200
        listed = client.get(base).json()[0]
        assert not listed["valid"] and "bess1" in listed["problems"][0]


class TestBuiltins:
    @pytest.mark.parametrize("site", sorted(default_sites()))
    def test_every_builtin_fits_every_default_site(self, site: str) -> None:
        config = default_sites()[site]
        devices = build_layout(config, POINT_STANDARD)
        for name, scenario in BUILTIN_SCENARIOS.items():
            assert validate_scenario(scenario, config) == [], name
            assert expectation_problems(scenario, devices) == [], name
            assert scenario.description, name
            assert scenario.expected_points, name

    @pytest.mark.parametrize("name", sorted(BUILTIN_SCENARIOS))
    def test_builtin_expected_points_hold(self, name: str) -> None:
        """Play the scenario on the reference site and check every expected point on every
        step of its window, as the Modbus server would serve it."""
        config = default_site("2bess_1pv")
        simulation = config.simulation.model_copy(update={"test_mode": True, "start_time": ORIGIN})
        config = config.model_copy(update={"simulation": simulation})
        engine = Engine(
            SiteRuntime.build(config, PROFILES, PandapowerSolver), PandapowerSolver, PROFILES
        )
        registry = PointRegistry(engine, SetpointService(engine))
        devices = build_layout(engine.config, POINT_STANDARD)
        scenario = BUILTIN_SCENARIOS[name]
        asyncio.run(engine.start_scenario(name, scenario))
        last = max(expected.last_step for expected in scenario.expected_points)
        failures: list[str] = []
        for step in range(1, last + 1):
            snapshot = asyncio.run(engine.step(1))
            sources = sources_from(snapshot, engine.config, registry, POINT_STANDARD.enums)
            failures += failures_at(scenario, step, devices, sources)
        assert failures == []

    def test_expected_points_are_checked_against_the_layout(self) -> None:
        devices = build_layout(default_site("2bess_1pv"), POINT_STANDARD)

        def problems(**fields: Any) -> list[str]:
            expected = ExpectedPoint.model_validate({"from_step": 1, **fields})
            scenario = EventScenario(events=[open_at(1)], expected_points=[expected])
            return expectation_problems(scenario, devices)

        assert problems(device="bess.bess1", point="InvSt", equals="FAULT") == []
        assert "no device" in problems(device="bess.bess9", point="InvSt", equals=0)[0]
        assert "no point" in problems(device="bess.bess1", point="Nope", equals=0)[0]
        assert "no value" in problems(device="bess.bess1", point="InvSt", equals="BROKEN")[0]
        assert "no bit" in problems(device="bess.bess1", point="Alrm", bits_set=["NOPE"])[0]
        assert "simulated" in problems(device="bess.bess1", point="TmpCab", equals=0)[0]
        with pytest.raises(ValueError):
            ExpectedPoint(device="bess.bess1", point="W", from_step=1)  # nothing to check
        with pytest.raises(ValueError):
            ExpectedPoint(device="bess.bess1", point="W", equals=0, from_step=5, to_step=2)

    def test_a_wrong_expectation_fails(self) -> None:
        config = default_site("2bess_1pv")
        simulation = config.simulation.model_copy(update={"test_mode": True, "start_time": ORIGIN})
        config = config.model_copy(update={"simulation": simulation})
        engine = Engine(
            SiteRuntime.build(config, PROFILES, PandapowerSolver), PandapowerSolver, PROFILES
        )
        registry = PointRegistry(engine, SetpointService(engine))
        devices = build_layout(engine.config, POINT_STANDARD)
        wrong = EventScenario(
            events=[open_at(1)],
            expected_points=[
                ExpectedPoint(device="bess.bess1", point="InvSt", equals="FAULT", from_step=1),
                ExpectedPoint(device="bess.bess1", point="BrkPos", equals=2, from_step=1),
                ExpectedPoint(
                    device="bess.bess1", point="Alrm", bits_clear=["AC_DISCONNECT"], from_step=1
                ),
            ],
        )
        asyncio.run(engine.start_scenario("wrong", wrong))
        snapshot = asyncio.run(engine.step(1))
        sources = sources_from(snapshot, engine.config, registry, POINT_STANDARD.enums)
        assert failures_at(wrong, 1, devices, sources) == [
            "step 1: bess.bess1.InvSt is OFF, expected FAULT",
            "step 1: bess.bess1.BrkPos is 1, expected 2 ± 0",
            "step 1: bess.bess1.Alrm has bit AC_DISCONNECT set",
        ]

    def test_a_bad_expected_point_is_refused_on_save(self, client: TestClient) -> None:
        body = {
            **SCENARIO_BODY,
            "expected_points": [
                {"device": "bess.bess9", "point": "InvSt", "equals": "FAULT", "from_step": 1}
            ],
        }
        response = client.put(f"/api/sites/{TEST_SITE}/event-scenarios/bad", json=body)
        assert response.status_code == 422 and "bess.bess9" in response.json()["detail"]

    def test_synced_to_default_sites_only_and_read_only(self, client: TestClient) -> None:
        default_site = sorted(default_sites())[0]
        listed = client.get(f"/api/sites/{default_site}/event-scenarios").json()
        assert {item["name"] for item in listed} == set(BUILTIN_SCENARIOS)
        assert all(item["category"] == "default" and item["valid"] for item in listed)
        assert client.get(f"/api/sites/{TEST_SITE}/event-scenarios").json() == []  # custom site
        base = f"/api/sites/{default_site}/event-scenarios/poi-trip"
        assert client.delete(base).status_code == 409
        edited = {**SCENARIO_BODY, "description": "my edit"}
        assert client.put(base, json=edited).status_code == 409  # read-only
        copy = f"/api/sites/{default_site}/event-scenarios/my-poi-trip"
        assert client.put(copy, json=edited).status_code == 200  # a copy is custom
        listed = {
            item["name"]: item
            for item in client.get(f"/api/sites/{default_site}/event-scenarios").json()
        }
        assert listed["my-poi-trip"]["category"] == "custom"
        assert listed["poi-trip"]["description"] == BUILTIN_SCENARIOS["poi-trip"].description

    def test_sync_updates_stale_builtins_and_drops_retired_ones(self, client: TestClient) -> None:
        context = client.app.state.context  # type: ignore[attr-defined]
        assert asyncio.run(context.scenarios.sync_builtins()) == 0  # already in sync
        repository = context.scenarios._repository
        default_site = sorted(default_sites())[0]
        old = EventScenario(description="an old copy", events=[open_at(1)])
        asyncio.run(repository.sync_builtin_event_scenario(default_site, "poi-trip", old))
        asyncio.run(repository.sync_builtin_event_scenario(default_site, "retired", old))
        assert asyncio.run(context.scenarios.sync_builtins()) == 2
        assert (
            asyncio.run(repository.get_event_scenario(default_site, "poi-trip"))
            == (BUILTIN_SCENARIOS["poi-trip"])
        )
        names = {item.name for item in asyncio.run(repository.list_event_scenarios(default_site))}
        assert "retired" not in names

    def test_latched_builtin_plays_deterministically(self) -> None:
        engine = make_engine()
        scenario = BUILTIN_SCENARIOS["bess1-over-temperature-latched"]
        asyncio.run(engine.start_scenario("latched", scenario))
        statuses = {step: asyncio.run(engine.step(1)).bess[0].status for step in range(1, 92)}
        assert statuses[4] != BessStatus.FAULT
        assert statuses[5] == statuses[60] == statuses[89] == BessStatus.FAULT  # latched at 60
        assert statuses[90] != BessStatus.FAULT  # alarm reset
